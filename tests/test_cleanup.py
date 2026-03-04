"""Tests for app/services/cleanup_service.py — mocked database + real moto S3."""
from unittest.mock import patch, call

import boto3
import pytest

from app.services import cleanup_service

_EXPIRED_FILE = {
    "file_id": "old-file-1",
    "stored_name": "uploads/old-file-1",
}

_EXPIRED_FILE_2 = {
    "file_id": "old-file-2",
    "stored_name": "uploads/old-file-2",
}


class TestCleanupExpired:
    def test_deletes_s3_objects_and_db_records(self, aws_mock):
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.put_object(Bucket="test-bucket", Key="uploads/old-file-1", Body=b"stale")
        s3.put_object(Bucket="test-bucket", Key="uploads/old-file-2", Body=b"stale")

        with patch.object(
            cleanup_service.db_helpers, "collect_expired_files", return_value=[_EXPIRED_FILE, _EXPIRED_FILE_2]
        ):
            with patch.object(cleanup_service.db_helpers, "delete_file_record") as mock_del:
                with patch.object(cleanup_service.db_helpers, "delete_expired_slugs") as mock_slugs:
                    cleanup_service.cleanup_expired()

        mock_del.assert_any_call("old-file-1")
        mock_del.assert_any_call("old-file-2")
        assert mock_del.call_count == 2

        # S3 objects should be deleted
        resp = s3.list_objects_v2(Bucket="test-bucket", Prefix="uploads/")
        assert resp.get("KeyCount", 0) == 0

        mock_slugs.assert_called_once()

    def test_s3_error_does_not_abort_db_delete(self, aws_mock):
        # S3 object does not exist — S3 delete will raise, but DB delete should still happen
        with patch.object(
            cleanup_service.db_helpers, "collect_expired_files", return_value=[_EXPIRED_FILE]
        ):
            with patch.object(cleanup_service.db_helpers, "delete_file_record") as mock_del:
                with patch.object(cleanup_service.db_helpers, "delete_expired_slugs"):
                    cleanup_service.cleanup_expired()

        mock_del.assert_called_once_with("old-file-1")

    def test_always_calls_delete_expired_slugs(self, aws_mock):
        with patch.object(
            cleanup_service.db_helpers, "collect_expired_files", return_value=[]
        ):
            with patch.object(cleanup_service.db_helpers, "delete_expired_slugs") as mock_slugs:
                cleanup_service.cleanup_expired()

        mock_slugs.assert_called_once()

    def test_lambda_handler_calls_cleanup(self, aws_mock):
        with patch.object(cleanup_service, "cleanup_expired") as mock_cleanup:
            cleanup_service.lambda_handler({}, {})
        mock_cleanup.assert_called_once()
