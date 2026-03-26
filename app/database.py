"""DynamoDB data layer."""
import time
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.config import settings

_dynamodb = None


def _db():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
    return _dynamodb


def _tokens():
    return _db().Table(settings.dynamodb_table_tokens)


def _slugs():
    return _db().Table(settings.dynamodb_table_slugs)


def _files():
    return _db().Table(settings.dynamodb_table_files)


def _notes():
    return _db().Table(settings.dynamodb_table_notes)


def _n(v) -> Decimal:
    """Convert int/float to Decimal for DynamoDB Number attributes."""
    return Decimal(str(v))


# ---------------------------------------------------------------------------
# Token queries
# ---------------------------------------------------------------------------

def get_active_token(token: str) -> dict | None:
    resp = _tokens().get_item(Key={"token": token})
    item = resp.get("Item")
    if item and int(item.get("is_active", 0)) == 1:
        return item
    return None


def insert_token(token: str, label: str | None) -> None:
    _tokens().put_item(Item={
        "token": token,
        "label": label or "",
        "created_at": _n(time.time()),
        "is_active": 1,
    })


def list_tokens() -> list[dict]:
    resp = _tokens().scan()
    items = resp.get("Items", [])
    return sorted(items, key=lambda x: float(x.get("created_at", 0)), reverse=True)


def revoke_token(token: str) -> bool:
    try:
        _tokens().update_item(
            Key={"token": token},
            UpdateExpression="SET is_active = :zero",
            ConditionExpression="attribute_exists(#t)",
            ExpressionAttributeNames={"#t": "token"},
            ExpressionAttributeValues={":zero": 0},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


# ---------------------------------------------------------------------------
# Slug queries
# ---------------------------------------------------------------------------

def get_slug_row(slug: str) -> dict | None:
    resp = _slugs().get_item(Key={"slug": slug})
    item = resp.get("Item")
    if item and float(item["expires_at"]) > time.time():
        return item
    return None


def insert_slug(slug: str) -> dict:
    now = time.time()
    expires_at = now + settings.slug_ttl_seconds
    item = {
        "slug": slug,
        "created_at": _n(now),
        "expires_at": _n(expires_at),
        "storage_used_bytes": _n(0),
        "ttl": int(expires_at),
    }
    try:
        _slugs().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(slug)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(status_code=409, detail="Slug already taken.")
        raise
    return item


def reserve_storage(slug: str, size_bytes: int) -> None:
    """Atomically add size_bytes to storage quota. Raises HTTP 413 if limit would be exceeded."""
    try:
        _slugs().update_item(
            Key={"slug": slug},
            UpdateExpression="ADD storage_used_bytes :size",
            ConditionExpression="storage_used_bytes <= :remaining",
            ExpressionAttributeValues={
                ":size": _n(size_bytes),
                # Equivalent to: storage_used_bytes + size_bytes <= max
                ":remaining": _n(settings.max_slug_storage_bytes - size_bytes),
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise HTTPException(status_code=413, detail="Storage limit reached for this slug.")
        raise


def release_storage(slug: str, size_bytes: int) -> None:
    """Subtract size_bytes from storage quota when a file is deleted."""
    _slugs().update_item(
        Key={"slug": slug},
        UpdateExpression="ADD storage_used_bytes :neg",
        ExpressionAttributeValues={":neg": _n(-size_bytes)},
    )


# ---------------------------------------------------------------------------
# File queries
# ---------------------------------------------------------------------------

def insert_file_record(
    file_id: str,
    slug: str,
    original_name: str,
    stored_name: str,
    size_bytes: int,
    expires_at: float,
) -> dict:
    now = time.time()
    item = {
        "file_id": file_id,
        "slug": slug,
        "original_name": original_name,
        "stored_name": stored_name,
        "size_bytes": _n(size_bytes),
        "uploaded_at": _n(now),
        "expires_at": _n(expires_at),
        "status": "pending",
        "ttl": int(expires_at),
    }
    _files().put_item(Item=item)
    return item


def update_file_confirmed(file_id: str, md5: str) -> dict | None:
    try:
        resp = _files().update_item(
            Key={"file_id": file_id},
            UpdateExpression="SET #s = :active, md5 = :md5",
            ConditionExpression="attribute_exists(file_id)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":active": "active", ":md5": md5},
            ReturnValues="ALL_NEW",
        )
        return resp.get("Attributes")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise


def list_files(slug: str) -> list[dict]:
    resp = _files().query(
        IndexName="slug-index",
        KeyConditionExpression=Key("slug").eq(slug),
        FilterExpression=Attr("status").eq("active"),
    )
    items = resp.get("Items", [])
    return sorted(items, key=lambda x: float(x.get("uploaded_at", 0)))


def get_file_record(file_id: str, slug: str) -> dict | None:
    resp = _files().get_item(Key={"file_id": file_id})
    item = resp.get("Item")
    if item and item.get("slug") == slug:
        return item
    return None


def delete_file_record(file_id: str) -> None:
    _files().delete_item(Key={"file_id": file_id})


# ---------------------------------------------------------------------------
# Cleanup queries
# ---------------------------------------------------------------------------

def collect_expired_files() -> list[dict]:
    """Return all file records with expires_at < now (for cleanup Lambda)."""
    now = time.time()
    resp = _files().scan(FilterExpression=Attr("expires_at").lt(_n(now)))
    return resp.get("Items", [])


# ---------------------------------------------------------------------------
# Note queries
# ---------------------------------------------------------------------------

def insert_note(
    slug: str,
    content: str,
    note_type: str,
    preview: dict,
    expires_at: float,
) -> dict:
    now = time.time()
    note_id = str(uuid.uuid4())
    item: dict = {
        "note_id": note_id,
        "slug": slug,
        "content": content,
        "note_type": note_type,
        "created_at": _n(now),
        "expires_at": _n(expires_at),
        "ttl": int(expires_at),
    }
    for key in ("title", "description", "image", "domain"):
        if preview.get(key):
            item[f"preview_{key}"] = preview[key]
    _notes().put_item(Item=item)
    return item


def list_notes(slug: str) -> list[dict]:
    resp = _notes().query(
        IndexName="slug-index",
        KeyConditionExpression=Key("slug").eq(slug),
    )
    items = resp.get("Items", [])
    return sorted(items, key=lambda x: float(x.get("created_at", 0)))


def get_note_record(note_id: str, slug: str) -> dict | None:
    resp = _notes().get_item(Key={"note_id": note_id})
    item = resp.get("Item")
    if item and item.get("slug") == slug:
        return item
    return None


def delete_note_record(note_id: str) -> None:
    _notes().delete_item(Key={"note_id": note_id})


def collect_expired_notes() -> list[dict]:
    now = time.time()
    resp = _notes().scan(FilterExpression=Attr("expires_at").lt(_n(now)))
    return resp.get("Items", [])


def delete_expired_slugs() -> None:
    """Delete all slug records with expires_at < now (belt-and-suspenders alongside DynamoDB TTL)."""
    now = time.time()
    resp = _slugs().scan(FilterExpression=Attr("expires_at").lt(_n(now)))
    for item in resp.get("Items", []):
        _slugs().delete_item(Key={"slug": item["slug"]})
