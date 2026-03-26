from fastapi import HTTPException

from app import database as db_helpers
from app.models import FileInfo, SlugInfo
from app.services.note_service import list_notes


def create_slug(slug: str) -> SlugInfo:
    row = db_helpers.insert_slug(slug)  # raises HTTP 409 if already taken
    return SlugInfo(
        slug=row["slug"],
        created_at=float(row["created_at"]),
        expires_at=float(row["expires_at"]),
        storage_used_bytes=0,
        files=[],
        notes=[],
    )


def get_slug_info(slug: str) -> SlugInfo:
    row = db_helpers.get_slug_row(slug)
    if not row:
        raise HTTPException(status_code=404, detail="Slug not found or expired.")

    file_rows = db_helpers.list_files(slug)
    files = [
        FileInfo(
            id=f["file_id"],
            original_name=f["original_name"],
            size_bytes=int(f["size_bytes"]),
            uploaded_at=float(f["uploaded_at"]),
            expires_at=float(f["expires_at"]),
            md5=f.get("md5"),
        )
        for f in file_rows
    ]
    storage_used = int(row.get("storage_used_bytes", 0))

    return SlugInfo(
        slug=row["slug"],
        created_at=float(row["created_at"]),
        expires_at=float(row["expires_at"]),
        storage_used_bytes=storage_used,
        files=files,
        notes=list_notes(slug),
    )
