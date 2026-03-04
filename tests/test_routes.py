"""Tests for app/routes/api.py — FastAPI endpoints via TestClient."""
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.config
from app.main import app
from app.models import FileInfo, PresignResponse, SlugInfo

# Shared mock data
_SLUG_INFO = SlugInfo(
    slug="test-slug",
    created_at=1700000000.0,
    expires_at=9999999999.0,
    storage_used_bytes=0,
    files=[],
)

_FILE_INFO = FileInfo(
    id="file-uuid-1",
    original_name="test.txt",
    size_bytes=1024,
    uploaded_at=1700000100.0,
    expires_at=9999999999.0,
    md5="aabbcc",
)

_PRESIGN_RESP = PresignResponse(
    file_id="file-uuid-1",
    upload_url="https://s3.example.com/presigned-url",
)


@pytest.fixture
def client(monkeypatch):
    """TestClient with beta_mode disabled (no auth required)."""
    monkeypatch.setattr(app.config.settings, "beta_mode", False)
    return TestClient(app)


@pytest.fixture
def beta_client(monkeypatch):
    """TestClient with beta_mode enabled (auth required)."""
    monkeypatch.setattr(app.config.settings, "beta_mode", True)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

class TestAuthStatus:
    def test_unauthenticated(self, client):
        r = client.get("/api/auth/status")
        assert r.status_code == 200
        data = r.json()
        assert data["authenticated"] is False
        assert data["beta_mode"] is False

    def test_beta_mode_reflected(self, beta_client):
        r = beta_client.get("/api/auth/status")
        assert r.status_code == 200
        assert r.json()["beta_mode"] is True


class TestAuthLogin:
    def test_valid_token(self, client):
        with patch("app.routes.api.db_helpers.get_active_token", return_value={"token": "good"}):
            r = client.post("/api/auth", json={"token": "good-token"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_invalid_token(self, client):
        with patch("app.routes.api.db_helpers.get_active_token", return_value=None):
            r = client.post("/api/auth", json={"token": "bad-token"})
        assert r.status_code == 401

    def test_logout(self, client):
        r = client.post("/api/auth/logout")
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ---------------------------------------------------------------------------
# Slug endpoints
# ---------------------------------------------------------------------------

class TestCreateSlug:
    def test_success(self, client):
        with patch("app.routes.api.slug_service.create_slug", return_value=_SLUG_INFO):
            r = client.post("/api/slugs", json={"slug": "test-slug"})
        assert r.status_code == 201
        assert r.json()["slug"] == "test-slug"

    def test_invalid_slug_body(self, client):
        # Pydantic rejects the slug before it reaches the service
        r = client.post("/api/slugs", json={"slug": "-bad"})
        assert r.status_code == 422

    def test_conflict(self, client):
        with patch(
            "app.routes.api.slug_service.create_slug",
            side_effect=HTTPException(status_code=409, detail="Slug already taken."),
        ):
            r = client.post("/api/slugs", json={"slug": "taken-slug"})
        assert r.status_code == 409

    def test_beta_mode_requires_auth(self, beta_client):
        r = beta_client.post("/api/slugs", json={"slug": "test-slug"})
        assert r.status_code == 401


class TestGetSlug:
    def test_success(self, client):
        with patch("app.routes.api.slug_service.get_slug_info", return_value=_SLUG_INFO):
            r = client.get("/api/slugs/test-slug")
        assert r.status_code == 200
        assert r.json()["slug"] == "test-slug"

    def test_not_found(self, client):
        with patch(
            "app.routes.api.slug_service.get_slug_info",
            side_effect=HTTPException(status_code=404, detail="Slug not found or expired."),
        ):
            r = client.get("/api/slugs/missing")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# File endpoints
# ---------------------------------------------------------------------------

class TestPresign:
    def test_success(self, client):
        with patch("app.routes.api.db_helpers.get_slug_row", return_value={"slug": "test-slug"}):
            with patch("app.routes.api.file_service.create_presigned_upload", return_value=_PRESIGN_RESP):
                r = client.post("/api/slugs/test-slug/files/presign", json={"filename": "a.txt", "size_bytes": 1024})
        assert r.status_code == 201
        assert r.json()["file_id"] == "file-uuid-1"

    def test_slug_not_found(self, client):
        with patch("app.routes.api.db_helpers.get_slug_row", return_value=None):
            r = client.post("/api/slugs/no-slug/files/presign", json={"filename": "a.txt", "size_bytes": 1})
        assert r.status_code == 404


class TestConfirm:
    def test_success(self, client):
        with patch("app.routes.api.db_helpers.get_slug_row", return_value={"slug": "test-slug"}):
            with patch("app.routes.api.file_service.confirm_upload", return_value=_FILE_INFO):
                r = client.post("/api/slugs/test-slug/files/file-uuid-1/confirm")
        assert r.status_code == 200
        assert r.json()["id"] == "file-uuid-1"

    def test_slug_not_found(self, client):
        with patch("app.routes.api.db_helpers.get_slug_row", return_value=None):
            r = client.post("/api/slugs/no-slug/files/file-uuid-1/confirm")
        assert r.status_code == 404


class TestDownload:
    def test_redirects(self, client):
        with patch("app.routes.api.db_helpers.get_slug_row", return_value={"slug": "test-slug"}):
            with patch(
                "app.routes.api.file_service.get_download_url",
                return_value="https://s3.example.com/presigned-download",
            ):
                r = client.get("/api/slugs/test-slug/files/file-uuid-1/download", allow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"] == "https://s3.example.com/presigned-download"

    def test_slug_not_found(self, client):
        with patch("app.routes.api.db_helpers.get_slug_row", return_value=None):
            r = client.get("/api/slugs/no-slug/files/file-uuid-1/download", allow_redirects=False)
        assert r.status_code == 404


class TestDeleteFile:
    def test_success(self, client):
        with patch("app.routes.api.db_helpers.get_slug_row", return_value={"slug": "test-slug"}):
            with patch("app.routes.api.file_service.delete_file"):
                r = client.delete("/api/slugs/test-slug/files/file-uuid-1")
        assert r.status_code == 204

    def test_slug_not_found(self, client):
        with patch("app.routes.api.db_helpers.get_slug_row", return_value=None):
            r = client.delete("/api/slugs/no-slug/files/file-uuid-1")
        assert r.status_code == 404
