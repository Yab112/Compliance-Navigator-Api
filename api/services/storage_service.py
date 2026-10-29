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


UPLOAD_ROOT = Path("uploads")
ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def save_agent_file(content: bytes, filename: str, content_type: str | None, *, public: bool) -> str:
    """
    Agent photos are public (served at /uploads/public/...); ID documents are
    private and only reachable through the admin file endpoint.
    """
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise ValueError("Only JPG, PNG, WEBP or PDF files are accepted")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Files must be 5 MB or smaller")
    if is_s3_configured():
        return upload_file(content, filename, prefix="guday/public" if public else "guday/private",
                           content_type=content_type)

    folder = "public" if public else "private"
    safe_name = f"{uuid.uuid4()}{Path(filename).suffix.lower()[:8]}"
    dest = UPLOAD_ROOT / folder / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return f"/uploads/public/{safe_name}" if public else f"private/{safe_name}"


IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def delete_public_file(url: str | None) -> None:
    """Remove a replaced photo or logo we stored locally; anything else is left alone."""
    if not url or not url.startswith("/uploads/public/"):
        return
    base = (UPLOAD_ROOT / "public").resolve()
    path = (UPLOAD_ROOT / "public" / url.removeprefix("/uploads/public/")).resolve()
    if base in path.parents and path.is_file():
        path.unlink()


def private_file_path(key: str) -> Path | None:
    """Resolve a 'private/<name>' key to a local file, refusing path traversal."""
    if not key.startswith("private/"):
        return None
    base = (UPLOAD_ROOT / "private").resolve()
    path = (UPLOAD_ROOT / key).resolve()
    if base not in path.parents or not path.is_file():
        return None
    return path
