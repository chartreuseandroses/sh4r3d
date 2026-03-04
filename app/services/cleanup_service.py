"""Cleanup Lambda handler — invoked by EventBridge on a schedule."""
import logging

import boto3

from app import database as db_helpers
from app.config import settings

logger = logging.getLogger(__name__)


def cleanup_expired() -> None:
    s3 = boto3.client("s3", region_name=settings.aws_region)
    expired_files = db_helpers.collect_expired_files()
    deleted = 0

    for record in expired_files:
        stored_name = record.get("stored_name")
        file_id = record.get("file_id")

        if stored_name:
            try:
                s3.delete_object(Bucket=settings.s3_bucket, Key=stored_name)
            except Exception:
                logger.exception("Failed to delete S3 object %s", stored_name)

        if file_id:
            try:
                db_helpers.delete_file_record(file_id)
                deleted += 1
            except Exception:
                logger.exception("Failed to delete file record %s", file_id)

    # Belt-and-suspenders: also delete expired slug records (DynamoDB TTL handles this too)
    db_helpers.delete_expired_slugs()

    if deleted:
        logger.info("Cleanup: removed %d expired file(s).", deleted)


def lambda_handler(event, context):
    """EventBridge scheduled invocation entry point."""
    try:
        cleanup_expired()
    except Exception:
        logger.exception("Cleanup Lambda failed.")
