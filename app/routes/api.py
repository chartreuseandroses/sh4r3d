from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import database as db_helpers
from app.config import settings
from app.models import AuthRequest, FileInfo, PresignRequest, PresignResponse, SlugCreate, SlugInfo
from app.services import file_service, slug_service

router = APIRouter()


def require_api_auth(request: Request) -> None:
    if settings.beta_mode and not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Authentication required.")


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/auth")
def auth_login(request: Request, body: AuthRequest):
    row = db_helpers.get_active_token(body.token.strip())
    if not row:
        raise HTTPException(status_code=401, detail="Invalid token.")
    request.session["authenticated"] = True
    return {"ok": True}


@router.post("/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/auth/status")
def auth_status(request: Request):
    """Called by every page on load to check auth state."""
    return {
        "authenticated": bool(request.session.get("authenticated")),
        "beta_mode": settings.beta_mode,
    }


# ---------------------------------------------------------------------------
# Slug endpoints
# ---------------------------------------------------------------------------

@router.post("/slugs", status_code=201)
def create_slug(body: SlugCreate, _=Depends(require_api_auth)) -> SlugInfo:
    return slug_service.create_slug(body.slug)


@router.get("/slugs/{slug}")
def get_slug(slug: str, _=Depends(require_api_auth)) -> SlugInfo:
    return slug_service.get_slug_info(slug)


# ---------------------------------------------------------------------------
# File endpoints
# ---------------------------------------------------------------------------

@router.post("/slugs/{slug}/files/presign", status_code=201)
def presign_upload(
    slug: str, body: PresignRequest, _=Depends(require_api_auth)
) -> PresignResponse:
    slug_row = db_helpers.get_slug_row(slug)
    if not slug_row:
        raise HTTPException(status_code=404, detail="Slug not found or expired.")
    return file_service.create_presigned_upload(slug_row, body.filename, body.size_bytes)


@router.post("/slugs/{slug}/files/{file_id}/confirm")
def confirm_upload(
    slug: str, file_id: str, _=Depends(require_api_auth)
) -> FileInfo:
    slug_row = db_helpers.get_slug_row(slug)
    if not slug_row:
        raise HTTPException(status_code=404, detail="Slug not found or expired.")
    return file_service.confirm_upload(slug_row, file_id)


@router.get("/slugs/{slug}/files/{file_id}/download")
def download_file(slug: str, file_id: str, _=Depends(require_api_auth)):
    slug_row = db_helpers.get_slug_row(slug)
    if not slug_row:
        raise HTTPException(status_code=404, detail="Slug not found or expired.")
    url = file_service.get_download_url(file_id, slug)
    return RedirectResponse(url=url, status_code=302)


@router.delete("/slugs/{slug}/files/{file_id}", status_code=204)
def delete_file(slug: str, file_id: str, _=Depends(require_api_auth)):
    slug_row = db_helpers.get_slug_row(slug)
    if not slug_row:
        raise HTTPException(status_code=404, detail="Slug not found or expired.")
    file_service.delete_file(file_id, slug)
