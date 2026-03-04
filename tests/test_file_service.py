"""Tests for app/services/file_service.py — real moto S3 + mocked database layer."""
import time
from decimal import Decimal
from unittest.mock import patch, MagicMock

import boto3
import pytest
from fastapi import HTTPException

from app.services import file_service

_SLUG_ROW = {
    "slug": "share-slug",
    "created_at": Decimal("1700000000"),
    "expires_at": Decimal(str(time.time() + 86400)),
    "storage_used_bytes": Decimal("0"),
}

_FILE_RECORD = {
    "file_id": "file-uuid-abc",
    "slug": "share-slug",
    "original_name": "photo.png",
    "stored_name": "uploads/file-uuid-abc",
    "size_bytes": Decimal("4096"),
    "uploaded_at": Decimal("1700000100"),
    "expires_at": Decimal(str(time.time() + 86400)),
    "status": "active",
    "md5": None,
}

_CONFIRMED_RECORD = {**_FILE_RECORD, "status": "active", "md5": "aabbcc"}


class TestCreatePresignedUpload:
    def test_returns_presign_response(self, aws_mock):
        with patch.object(file_service.db_helpers, "reserve_storage") as mock_reserve:
            with patch.object(file_service.db_helpers, "insert_file_record", return_value=_FILE_RECORD):
                result = file_service.create_presigned_upload(_SLUG_ROW, "photo.png", 4096)

        mock_reserve.assert_called_once_with("share-slug", 4096)
        assert result.file_id  # some UUID
        assert result.upload_url.startswith("https://")

    def test_propagates_413_from_reserve(self, aws_mock):
        with patch.object(
            file_service.db_helpers,
            "reserve_storage",
            side_effect=HTTPException(status_code=413, detail="Storage limit reached."),
        ):
            with pytest.raises(HTTPException) as exc_info:
                file_service.create_presigned_upload(_SLUG_ROW, "big.zip", 9_999_999_999)
        assert exc_info.value.status_code == 413


class TestConfirmUpload:
    def test_success(self, aws_mock):
        # Put an object in the moto S3 bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.put_object(Bucket="test-bucket", Key="uploads/file-uuid-abc", Body=b"data")

        with patch.object(file_service.db_helpers, "get_file_record", return_value=_FILE_RECORD):
            with patch.object(
                file_service.db_helpers, "update_file_confirmed", return_value=_CONFIRMED_RECORD
            ):
                result = file_service.confirm_upload(_SLUG_ROW, "file-uuid-abc")

        assert result.id == "file-uuid-abc"
        assert result.md5 == "aabbcc"

    def test_file_not_in_db(self, aws_mock):
        with patch.object(file_service.db_helpers, "get_file_record", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                file_service.confirm_upload(_SLUG_ROW, "missing-id")
        assert exc_info.value.status_code == 404

    def test_file_not_in_s3(self, aws_mock):
        # Record exists in DB but not in S3
        with patch.object(file_service.db_helpers, "get_file_record", return_value=_FILE_RECORD):
            with pytest.raises(HTTPException) as exc_info:
                file_service.confirm_upload(_SLUG_ROW, "file-uuid-abc")
        assert exc_info.value.status_code == 404


class TestGetDownloadUrl:
    def test_returns_presigned_url(self, aws_mock):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.put_object(Bucket="test-bucket", Key="uploads/file-uuid-abc", Body=b"content")

        with patch.object(file_service.db_helpers, "get_file_record", return_value=_FILE_RECORD):
            url = file_service.get_download_url("file-uuid-abc", "share-slug")

        assert url.startswith("https://")
        assert "file-uuid-abc" in url

    def test_file_not_found(self, aws_mock):
        with patch.object(file_service.db_helpers, "get_file_record", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                file_service.get_download_url("missing", "share-slug")
        assert exc_info.value.status_code == 404


class TestDeleteFile:
    def test_deletes_s3_and_db(self, aws_mock):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.put_object(Bucket="test-bucket", Key="uploads/file-uuid-abc", Body=b"x")

        with patch.object(file_service.db_helpers, "get_file_record", return_value=_FILE_RECORD):
            with patch.object(file_service.db_helpers, "delete_file_record") as mock_del:
                with patch.object(file_service.db_helpers, "release_storage") as mock_release:
                    file_service.delete_file("file-uuid-abc", "share-slug")

        mock_del.assert_called_once_with("file-uuid-abc")
        mock_release.assert_called_once_with("share-slug", 4096)

        # S3 object should be gone
        resp = s3.list_objects_v2(Bucket="test-bucket", Prefix="uploads/file-uuid-abc")
        assert resp.get("KeyCount", 0) == 0

    def test_file_not_found_raises_404(self, aws_mock):
        with patch.object(file_service.db_helpers, "get_file_record", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                file_service.delete_file("no-such", "share-slug")
        assert exc_info.value.status_code == 404
