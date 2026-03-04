"""Tests for app/database.py — all DynamoDB operations, mocked via moto."""
import time
from decimal import Decimal

import pytest
from fastapi import HTTPException

import app.database as db


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

class TestTokens:
    def test_insert_and_get_active(self, aws_mock):
        db.insert_token("tok-1", "Test label")
        result = db.get_active_token("tok-1")
        assert result is not None
        assert result["token"] == "tok-1"
        assert result["label"] == "Test label"

    def test_get_active_token_not_found(self, aws_mock):
        assert db.get_active_token("nonexistent") is None

    def test_get_active_token_revoked(self, aws_mock):
        db.insert_token("tok-2", "Will be revoked")
        db.revoke_token("tok-2")
        assert db.get_active_token("tok-2") is None

    def test_revoke_returns_true(self, aws_mock):
        db.insert_token("tok-3", "")
        assert db.revoke_token("tok-3") is True

    def test_revoke_nonexistent_returns_false(self, aws_mock):
        assert db.revoke_token("no-such-token") is False

    def test_list_tokens(self, aws_mock):
        db.insert_token("tok-a", "Alpha")
        db.insert_token("tok-b", "Beta")
        tokens = db.list_tokens()
        ids = {t["token"] for t in tokens}
        assert {"tok-a", "tok-b"}.issubset(ids)


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------

class TestSlugs:
    def test_insert_slug_returns_row(self, aws_mock):
        row = db.insert_slug("my-slug")
        assert row["slug"] == "my-slug"
        assert float(row["expires_at"]) > time.time()

    def test_insert_duplicate_raises_409(self, aws_mock):
        db.insert_slug("taken-slug")
        with pytest.raises(HTTPException) as exc_info:
            db.insert_slug("taken-slug")
        assert exc_info.value.status_code == 409

    def test_get_slug_row_found(self, aws_mock):
        db.insert_slug("active-slug")
        result = db.get_slug_row("active-slug")
        assert result is not None
        assert result["slug"] == "active-slug"

    def test_get_slug_row_not_found(self, aws_mock):
        assert db.get_slug_row("no-such-slug") is None

    def test_get_slug_row_expired(self, aws_mock):
        # Manually insert an expired slug
        import boto3
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.Table("test-slugs")
        table.put_item(Item={
            "slug": "old-slug",
            "created_at": Decimal("1000"),
            "expires_at": Decimal("1001"),  # already expired
            "storage_used_bytes": Decimal("0"),
            "ttl": 1001,
        })
        assert db.get_slug_row("old-slug") is None


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class TestStorage:
    def test_reserve_storage_success(self, aws_mock):
        db.insert_slug("quota-slug")
        db.reserve_storage("quota-slug", 100)
        row = db.get_slug_row("quota-slug")
        assert int(row["storage_used_bytes"]) == 100

    def test_reserve_storage_over_limit_raises_413(self, aws_mock):
        from app.config import settings
        db.insert_slug("full-slug")
        with pytest.raises(HTTPException) as exc_info:
            db.reserve_storage("full-slug", settings.max_slug_storage_bytes + 1)
        assert exc_info.value.status_code == 413

    def test_release_storage(self, aws_mock):
        db.insert_slug("release-slug")
        db.reserve_storage("release-slug", 500)
        db.release_storage("release-slug", 200)
        row = db.get_slug_row("release-slug")
        assert int(row["storage_used_bytes"]) == 300


# ---------------------------------------------------------------------------
# File records
# ---------------------------------------------------------------------------

class TestFileRecords:
    def _make_file(self, aws_mock, slug="test-slug", file_id="file-abc", status="active"):
        db.insert_slug(slug)
        future = time.time() + 86400
        db.insert_file_record(
            file_id=file_id,
            slug=slug,
            original_name="hello.txt",
            stored_name=f"uploads/{file_id}",
            size_bytes=1024,
            expires_at=future,
        )
        if status == "active":
            db.update_file_confirmed(file_id, "md5hash")

    def test_insert_file_record(self, aws_mock):
        db.insert_slug("s1")
        future = time.time() + 86400
        row = db.insert_file_record("f1", "s1", "a.txt", "uploads/f1", 512, future)
        assert row["file_id"] == "f1"
        assert row["status"] == "pending"

    def test_update_file_confirmed(self, aws_mock):
        db.insert_slug("s2")
        future = time.time() + 86400
        db.insert_file_record("f2", "s2", "b.txt", "uploads/f2", 256, future)
        updated = db.update_file_confirmed("f2", "abc123")
        assert updated["status"] == "active"
        assert updated["md5"] == "abc123"

    def test_update_file_confirmed_nonexistent(self, aws_mock):
        result = db.update_file_confirmed("no-such-id", "md5")
        assert result is None

    def test_list_files_only_active(self, aws_mock):
        db.insert_slug("s3")
        future = time.time() + 86400
        # pending file — should not appear
        db.insert_file_record("fp", "s3", "pending.txt", "uploads/fp", 100, future)
        # active file — should appear
        db.insert_file_record("fa", "s3", "active.txt", "uploads/fa", 200, future)
        db.update_file_confirmed("fa", "md5")

        files = db.list_files("s3")
        ids = [f["file_id"] for f in files]
        assert "fa" in ids
        assert "fp" not in ids

    def test_get_file_record(self, aws_mock):
        self._make_file(aws_mock, "s4", "f4")
        record = db.get_file_record("f4", "s4")
        assert record is not None
        assert record["file_id"] == "f4"

    def test_get_file_record_wrong_slug(self, aws_mock):
        self._make_file(aws_mock, "s5", "f5")
        assert db.get_file_record("f5", "different-slug") is None

    def test_delete_file_record(self, aws_mock):
        self._make_file(aws_mock, "s6", "f6")
        db.delete_file_record("f6")
        assert db.get_file_record("f6", "s6") is None


# ---------------------------------------------------------------------------
# Cleanup queries
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_collect_expired_files(self, aws_mock):
        import boto3
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.Table("test-files")
        table.put_item(Item={
            "file_id": "expired-file",
            "slug": "some-slug",
            "original_name": "old.txt",
            "stored_name": "uploads/expired-file",
            "size_bytes": Decimal("100"),
            "uploaded_at": Decimal("1000"),
            "expires_at": Decimal("1001"),  # past
            "status": "active",
            "ttl": 1001,
        })
        # Also insert a non-expired file
        future = time.time() + 86400
        db.insert_slug("slug-x")
        db.insert_file_record("fresh-file", "slug-x", "new.txt", "uploads/fresh", 50, future)

        expired = db.collect_expired_files()
        ids = [f["file_id"] for f in expired]
        assert "expired-file" in ids
        assert "fresh-file" not in ids

    def test_delete_expired_slugs(self, aws_mock):
        import boto3
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.Table("test-slugs")
        table.put_item(Item={
            "slug": "dead-slug",
            "created_at": Decimal("1000"),
            "expires_at": Decimal("1001"),
            "storage_used_bytes": Decimal("0"),
            "ttl": 1001,
        })
        db.insert_slug("live-slug")  # not expired

        db.delete_expired_slugs()

        # dead-slug record is deleted (get_slug_row already filters by expires_at,
        # but we can check directly via DynamoDB)
        result = ddb.Table("test-slugs").get_item(Key={"slug": "dead-slug"})
        assert "Item" not in result

        # live-slug is untouched
        assert db.get_slug_row("live-slug") is not None
