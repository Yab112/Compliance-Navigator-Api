"""S3 object storage for uploaded reference documents."""

from __future__ import annotations

import uuid
from pathlib import Path

from config.config import settings


def is_s3_configured() -> bool:
    return bool(
        settings.s3_bucket
        and settings.aws_access_key_id
        and settings.aws_secret_access_key
    )


def _client():
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.s3_endpoint_url or None,
    )


def upload_file(
    content: bytes,
    filename: str,
    *,
    prefix: str = "references",
    content_type: str | None = None,
) -> str:
    """
    Upload bytes to S3. Returns s3://bucket/key URI (or https URL if public).
    Falls back to local disk when S3 is not configured.
    """
    safe_name = Path(filename).name.replace(" ", "_")
    key = f"{prefix}/{uuid.uuid4()}_{safe_name}"

    if is_s3_configured():
        extra = {"ContentType": content_type} if content_type else {}
        _client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
            **extra,
        )
        if settings.s3_public_base_url:
            return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
        return f"s3://{settings.s3_bucket}/{key}"

    local_dir = Path(settings.upload_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    dest = local_dir / f"{uuid.uuid4()}_{safe_name}"
    dest.write_bytes(content)
    return str(dest)
