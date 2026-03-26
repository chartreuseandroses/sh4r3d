import html
import re
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app import database as db_helpers
from app.models import NoteInfo

URL_RE = re.compile(r"^https?://", re.IGNORECASE)

_OG_PROP_FIRST = re.compile(
    r'<meta[^>]+property=["\']og:(\w+)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_OG_CONT_FIRST = re.compile(
    r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:(\w+)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]{1,200})</title>", re.IGNORECASE)


def _fetch_preview(url: str) -> dict:
    try:
        req = Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; sh4r3d/1.0)"},
        )
        with urlopen(req, timeout=3) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                return {"domain": urlparse(url).netloc}
            raw = resp.read(65536)
        markup = raw.decode("utf-8", errors="replace")
    except Exception:
        return {"domain": urlparse(url).netloc}

    tags: dict[str, str] = {}
    for m in _OG_PROP_FIRST.finditer(markup):
        tags.setdefault(m.group(1), m.group(2))
    for m in _OG_CONT_FIRST.finditer(markup):
        tags.setdefault(m.group(2), m.group(1))

    if "title" not in tags:
        m = _TITLE_RE.search(markup)
        if m:
            tags["title"] = m.group(1).strip()

    if tags.get("image") and not URL_RE.match(tags["image"]):
        tags["image"] = urljoin(url, tags["image"])

    tags["domain"] = urlparse(url).netloc

    # Decode HTML entities (e.g. &#039; -> ') that sites embed in meta content
    for key in ("title", "description"):
        if key in tags:
            tags[key] = html.unescape(tags[key])

    return tags


def _to_note_info(row: dict) -> NoteInfo:
    return NoteInfo(
        id=row["note_id"],
        content=row["content"],
        note_type=row["note_type"],
        created_at=float(row["created_at"]),
        expires_at=float(row["expires_at"]),
        preview_title=row.get("preview_title"),
        preview_description=row.get("preview_description"),
        preview_image=row.get("preview_image"),
        preview_domain=row.get("preview_domain"),
    )


def create_note(slug_row: dict, content: str) -> NoteInfo:
    note_type = "url" if URL_RE.match(content.strip()) else "text"
    preview = _fetch_preview(content) if note_type == "url" else {}
    row = db_helpers.insert_note(
        slug=slug_row["slug"],
        content=content,
        note_type=note_type,
        preview=preview,
        expires_at=float(slug_row["expires_at"]),
    )
    return _to_note_info(row)


def list_notes(slug: str) -> list[NoteInfo]:
    return [_to_note_info(r) for r in db_helpers.list_notes(slug)]


def delete_note(note_id: str, slug: str) -> None:
    record = db_helpers.get_note_record(note_id, slug)
    if not record:
        raise HTTPException(status_code=404, detail="Note not found.")
    db_helpers.delete_note_record(note_id)
