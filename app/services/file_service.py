from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app import database as db_helpers
from app.config import settings
from app.models import FileInfo, PresignResponse

_s3 = None


def _s3_client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=settings.aws_region, config=Config(signature_version="s3v4"))
    return _s3


def create_presigned_upload(slug_row: dict, filename: str, size_bytes: int) -> PresignResponse:
    slug = slug_row["slug"]
    expires_at = float(slug_row["expires_at"])

    # Atomically reserve storage quota — raises HTTP 413 if limit would be exceeded
    db_helpers.reserve_storage(slug, size_bytes)

    file_id = str(uuid4())
    stored_name = f"uploads/{file_id}"

    db_helpers.insert_file_record(file_id, slug, filename, stored_name, size_bytes, expires_at)

    # Generate 15-minute presigned PUT URL (no Content-Type restriction)
    upload_url = _s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": stored_name},
        ExpiresIn=900,
    )
    return PresignResponse(file_id=file_id, upload_url=upload_url)


def confirm_upload(slug_row: dict, file_id: str) -> FileInfo:
    slug = slug_row["slug"]

    record = db_helpers.get_file_record(file_id, slug)
    if not record:
        raise HTTPException(status_code=404, detail="File record not found.")

    # Verify the file exists in S3 and read ETag (= MD5 for single-part uploads)
    try:
        head = _s3_client().head_object(
            Bucket=settings.s3_bucket, Key=record["stored_name"]
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("404", "NoSuchKey"):
            raise HTTPException(status_code=404, detail="File not found in storage.")
        raise

    etag = head.get("ETag", "").strip('"')  # S3 ETags include surrounding quotes

    updated = db_helpers.update_file_confirmed(file_id, etag)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to confirm upload.")

    return FileInfo(
        id=updated["file_id"],
        original_name=updated["original_name"],
        size_bytes=int(updated["size_bytes"]),
        uploaded_at=float(updated["uploaded_at"]),
        expires_at=float(updated["expires_at"]),
        md5=updated.get("md5"),
    )


def get_download_url(file_id: str, slug: str) -> str:
    record = db_helpers.get_file_record(file_id, slug)
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")

    return _s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": record["stored_name"],
            "ResponseContentDisposition": f'attachment; filename="{record["original_name"]}"',
        },
        ExpiresIn=300,  # 5-minute download window
    )


def delete_file(file_id: str, slug: str) -> None:
    record = db_helpers.get_file_record(file_id, slug)
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")

    # Best-effort S3 delete — continue even if object is already gone
    try:
        _s3_client().delete_object(
            Bucket=settings.s3_bucket, Key=record["stored_name"]
        )
    except ClientError:
        pass

    db_helpers.delete_file_record(file_id)
    db_helpers.release_storage(slug, int(record["size_bytes"]))
