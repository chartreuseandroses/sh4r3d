"""
Pytest configuration and shared fixtures.

IMPORTANT: env vars must be set before any app.* module is imported,
because app.config.settings = Settings() runs at import time.
"""
import os

# Set fake AWS credentials and app config before any app import
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-sessions")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("DYNAMODB_TABLE_TOKENS", "test-tokens")
os.environ.setdefault("DYNAMODB_TABLE_SLUGS", "test-slugs")
os.environ.setdefault("DYNAMODB_TABLE_FILES", "test-files")

import boto3
import pytest
from moto import mock_aws

import app.database as _db_module
import app.services.file_service as _fs_module


@pytest.fixture(autouse=True)
def reset_clients():
    """Reset cached boto3 clients before and after each test."""
    _db_module._dynamodb = None
    _fs_module._s3 = None
    yield
    _db_module._dynamodb = None
    _fs_module._s3 = None


@pytest.fixture
def aws_mock():
    """Start moto mocks and create the DynamoDB tables and S3 bucket."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        ddb.create_table(
            TableName="test-tokens",
            KeySchema=[{"AttributeName": "token", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "token", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        ddb.create_table(
            TableName="test-slugs",
            KeySchema=[{"AttributeName": "slug", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "slug", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        ddb.create_table(
            TableName="test-files",
            KeySchema=[{"AttributeName": "file_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "file_id", "AttributeType": "S"},
                {"AttributeName": "slug", "AttributeType": "S"},
                {"AttributeName": "uploaded_at", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "slug-index",
                "KeySchema": [
                    {"AttributeName": "slug", "KeyType": "HASH"},
                    {"AttributeName": "uploaded_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")

        yield
