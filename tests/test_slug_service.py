"""Tests for app/services/slug_service.py — mocking the database layer."""
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.services import slug_service

_SLUG_ROW = {
    "slug": "test-slug",
    "created_at": Decimal("1700000000"),
    "expires_at": Decimal("9999999999"),
    "storage_used_bytes": Decimal("512"),
}

_FILE_ROW = {
    "file_id": "file-uuid-1",
    "slug": "test-slug",
    "original_name": "report.pdf",
    "stored_name": "uploads/file-uuid-1",
    "size_bytes": Decimal("2048"),
    "uploaded_at": Decimal("1700000100"),
    "expires_at": Decimal("9999999999"),
    "status": "active",
    "md5": "deadbeef",
}


class TestCreateSlug:
    def test_returns_slug_info(self):
        with patch.object(slug_service.db_helpers, "insert_slug", return_value=_SLUG_ROW):
            result = slug_service.create_slug("test-slug")

        assert result.slug == "test-slug"
        assert result.storage_used_bytes == 0  # always 0 on creation
        assert result.files == []
        assert result.expires_at == float(_SLUG_ROW["expires_at"])

    def test_propagates_409(self):
        with patch.object(
            slug_service.db_helpers,
            "insert_slug",
            side_effect=HTTPException(status_code=409, detail="Slug already taken."),
        ):
            with pytest.raises(HTTPException) as exc_info:
                slug_service.create_slug("test-slug")
        assert exc_info.value.status_code == 409


class TestGetSlugInfo:
    def test_returns_slug_with_files(self):
        with patch.object(slug_service.db_helpers, "get_slug_row", return_value=_SLUG_ROW):
            with patch.object(slug_service.db_helpers, "list_files", return_value=[_FILE_ROW]):
                result = slug_service.get_slug_info("test-slug")

        assert result.slug == "test-slug"
        assert result.storage_used_bytes == 512
        assert len(result.files) == 1
        f = result.files[0]
        assert f.id == "file-uuid-1"
        assert f.original_name == "report.pdf"
        assert f.size_bytes == 2048
        assert f.md5 == "deadbeef"

    def test_returns_empty_file_list(self):
        with patch.object(slug_service.db_helpers, "get_slug_row", return_value=_SLUG_ROW):
            with patch.object(slug_service.db_helpers, "list_files", return_value=[]):
                result = slug_service.get_slug_info("test-slug")
        assert result.files == []

    def test_raises_404_when_not_found(self):
        with patch.object(slug_service.db_helpers, "get_slug_row", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                slug_service.get_slug_info("missing-slug")
        assert exc_info.value.status_code == 404
