"""
Integration tests — run against a live deployed application.

Each test creates its own uniquely-named slug (it-<random hex>) so tests are
independent and don't interfere with each other. Slugs and files auto-expire
after 24 hours, so left-over test data is cleaned up automatically.

Run:
  INTEGRATION_BASE_URL=https://sh4r3d.com INTEGRATION_TOKEN=<token> \
    pytest tests/integration/ -v
"""
import secrets

import httpx
import pytest


def _slug() -> str:
    """Generate a unique integration-test slug that satisfies the slug regex."""
    return f"it-{secrets.token_hex(4)}"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    def test_status_returns_expected_fields(self, api_client):
        r = api_client.get("/api/auth/status")
        assert r.status_code == 200
        data = r.json()
        assert "authenticated" in data
        assert "beta_mode" in data

    def test_invalid_token_rejected(self, api_client):
        r = api_client.post("/api/auth", json={"token": "definitely-not-a-real-token-xyz"})
        assert r.status_code == 401

    def test_logout(self, api_client):
        r = api_client.post("/api/auth/logout")
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------

class TestSlugEndpoints:
    def test_create_slug(self, api_client):
        slug = _slug()
        r = api_client.post("/api/slugs", json={"slug": slug})
        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == slug
        assert data["expires_at"] > 0
        assert data["storage_used_bytes"] == 0
        assert data["files"] == []

    def test_get_slug(self, api_client):
        slug = _slug()
        api_client.post("/api/slugs", json={"slug": slug})

        r = api_client.get(f"/api/slugs/{slug}")
        assert r.status_code == 200
        assert r.json()["slug"] == slug

    def test_duplicate_slug_rejected(self, api_client):
        slug = _slug()
        r1 = api_client.post("/api/slugs", json={"slug": slug})
        assert r1.status_code == 201

        r2 = api_client.post("/api/slugs", json={"slug": slug})
        assert r2.status_code == 409

    def test_missing_slug_returns_404(self, api_client):
        r = api_client.get("/api/slugs/this-slug-does-not-exist-at-all")
        assert r.status_code == 404

    def test_invalid_slug_format_rejected(self, api_client):
        r = api_client.post("/api/slugs", json={"slug": "-bad-slug-"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Full file lifecycle
# ---------------------------------------------------------------------------

class TestFileLifecycle:
    def test_presign_upload_confirm_download_delete(self, api_client):
        slug = _slug()
        content = b"integration test file content"
        filename = "test-upload.txt"

        # 1. Create slug
        r = api_client.post("/api/slugs", json={"slug": slug})
        assert r.status_code == 201

        # 2. Get presigned upload URL
        r = api_client.post(
            f"/api/slugs/{slug}/files/presign",
            json={"filename": filename, "size_bytes": len(content)},
        )
        assert r.status_code == 201
        presign = r.json()
        file_id = presign["file_id"]
        upload_url = presign["upload_url"]
        assert upload_url.startswith("https://")

        # 3. PUT file directly to S3 (bypasses the app entirely)
        with httpx.Client() as s3:
            put = s3.put(upload_url, content=content)
        assert put.status_code == 200, f"S3 PUT failed: {put.status_code} {put.text}"

        # 4. Confirm the upload
        r = api_client.post(f"/api/slugs/{slug}/files/{file_id}/confirm")
        assert r.status_code == 200
        confirmed = r.json()
        assert confirmed["id"] == file_id
        assert confirmed["original_name"] == filename
        assert confirmed["size_bytes"] == len(content)
        assert confirmed["md5"]  # ETag/MD5 must be present

        # 5. List files — confirmed file must appear
        r = api_client.get(f"/api/slugs/{slug}")
        assert r.status_code == 200
        files = r.json()["files"]
        ids = [f["id"] for f in files]
        assert file_id in ids
        assert r.json()["storage_used_bytes"] == len(content)

        # 6. Download — must redirect to a presigned S3 GET URL
        r = api_client.get(f"/api/slugs/{slug}/files/{file_id}/download")
        assert r.status_code == 302
        location = r.headers.get("location", "")
        assert location.startswith("https://")

        # Follow the redirect and verify we get the right content back
        with httpx.Client() as s3:
            dl = s3.get(location)
        assert dl.status_code == 200
        assert dl.content == content

        # 7. Delete
        r = api_client.delete(f"/api/slugs/{slug}/files/{file_id}")
        assert r.status_code == 204

        # 8. File must no longer appear in the listing
        r = api_client.get(f"/api/slugs/{slug}")
        assert r.status_code == 200
        files_after = r.json()["files"]
        assert not any(f["id"] == file_id for f in files_after)

    def test_presign_nonexistent_slug_returns_404(self, api_client):
        r = api_client.post(
            "/api/slugs/no-such-slug-xyz/files/presign",
            json={"filename": "x.txt", "size_bytes": 1},
        )
        assert r.status_code == 404

    def test_confirm_without_s3_upload_returns_404(self, api_client):
        slug = _slug()
        api_client.post("/api/slugs", json={"slug": slug})

        # Get a presign URL but don't PUT anything to S3
        r = api_client.post(
            f"/api/slugs/{slug}/files/presign",
            json={"filename": "ghost.txt", "size_bytes": 10},
        )
        assert r.status_code == 201
        file_id = r.json()["file_id"]

        # Confirm without uploading — should get 404 (not in S3)
        r = api_client.post(f"/api/slugs/{slug}/files/{file_id}/confirm")
        assert r.status_code == 404

    def test_delete_nonexistent_file_returns_404(self, api_client):
        slug = _slug()
        api_client.post("/api/slugs", json={"slug": slug})

        r = api_client.delete(f"/api/slugs/{slug}/files/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_multiple_files_in_slug(self, api_client):
        slug = _slug()
        api_client.post("/api/slugs", json={"slug": slug})

        uploaded_ids = []
        for i in range(3):
            content = f"file {i}".encode()

            r = api_client.post(
                f"/api/slugs/{slug}/files/presign",
                json={"filename": f"file{i}.txt", "size_bytes": len(content)},
            )
            assert r.status_code == 201
            file_id = r.json()["file_id"]
            upload_url = r.json()["upload_url"]

            with httpx.Client() as s3:
                s3.put(upload_url, content=content)

            r = api_client.post(f"/api/slugs/{slug}/files/{file_id}/confirm")
            assert r.status_code == 200
            uploaded_ids.append(file_id)

        r = api_client.get(f"/api/slugs/{slug}")
        listed_ids = [f["id"] for f in r.json()["files"]]
        for fid in uploaded_ids:
            assert fid in listed_ids
