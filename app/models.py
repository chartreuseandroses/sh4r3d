import re

from pydantic import BaseModel, field_validator

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")


class SlugCreate(BaseModel):
    slug: str

    @field_validator("slug")
    @classmethod
    def slug_must_be_valid(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(
                "Slug must be 3–64 characters, lowercase letters/numbers/hyphens, "
                "no leading or trailing hyphens."
            )
        return v


class FileInfo(BaseModel):
    id: str  # UUID string (DynamoDB file_id)
    original_name: str
    size_bytes: int
    uploaded_at: float
    expires_at: float
    md5: str | None = None


class NoteInfo(BaseModel):
    id: str
    content: str
    note_type: str  # "text" or "url"
    created_at: float
    expires_at: float
    preview_title: str | None = None
    preview_description: str | None = None
    preview_image: str | None = None
    preview_domain: str | None = None


class SlugInfo(BaseModel):
    slug: str
    created_at: float
    expires_at: float
    storage_used_bytes: int
    files: list[FileInfo]
    notes: list[NoteInfo] = []


class AuthRequest(BaseModel):
    token: str


class PresignRequest(BaseModel):
    filename: str
    size_bytes: int


class PresignResponse(BaseModel):
    file_id: str
    upload_url: str
