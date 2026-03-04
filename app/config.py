import secrets
import warnings

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Storage limits
    max_slug_storage_bytes: int = 500 * 1024 * 1024  # 500 MB
    slug_ttl_seconds: int = 86400  # 24 hours

    # Auth
    secret_key: str = ""
    beta_mode: bool = False

    # AWS — field names map to uppercase env vars (S3_BUCKET, AWS_REGION, etc.)
    aws_region: str = "us-east-1"
    s3_bucket: str = ""
    dynamodb_table_tokens: str = "sh4r3d-tokens"
    dynamodb_table_slugs: str = "sh4r3d-slugs"
    dynamodb_table_files: str = "sh4r3d-files"

    # Local dev only
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

if not settings.secret_key:
    settings.secret_key = secrets.token_hex(32)
    warnings.warn(
        "SECRET_KEY not set. Using a random key — sessions will be invalidated on restart. "
        "Set SECRET_KEY in your environment or .env file for production.",
        stacklevel=1,
    )
