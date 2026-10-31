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


def _put_object(key: str, content: bytes, content_type: str | None) -> None:
    """Store one object. No ACL is sent, so it stays private to the bucket owner; only a bucket policy
    on guday/public/ (photos and logos) may make anything readable without our credentials."""
    extra = {"ContentType": content_type} if content_type else {}
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=content, **extra)


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
        _put_object(key, content, content_type)
        if settings.s3_public_base_url:
            return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
        return f"s3://{settings.s3_bucket}/{key}"

    local_dir = Path(settings.upload_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    dest = local_dir / f"{uuid.uuid4()}_{safe_name}"
    dest.write_bytes(content)
    return str(dest)


UPLOAD_ROOT = Path("uploads")
S3_PUBLIC_PREFIX = "guday/public/"
S3_PRIVATE_PREFIX = "guday/private/"
S3_VETTING_PREFIX = "vetting/"
ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}


def save_agent_file(content: bytes, filename: str, content_type: str | None, *, public: bool) -> str:
    """
    Agent photos are public (served at /uploads/public/...); ID documents are
    private and only reachable through the admin file endpoint.

    The type comes from the file's first bytes, never from the name or the type the browser sent,
    and the stored extension follows the detected type, so nothing can be saved as .html or .svg.
    """
    detected = sniff_type(content)
    if detected not in ALLOWED_UPLOAD_TYPES:
        raise ValueError("Only JPG, PNG, WEBP or PDF files are accepted")
    declared = (content_type or "application/octet-stream").lower()
    if declared != "application/octet-stream" and declared != detected \
            and not (declared == "image/jpg" and detected == "image/jpeg"):
        raise ValueError("The file's content doesn't match its type. Upload a JPG, PNG, WEBP or PDF file.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Files must be 5 MB or smaller")
    safe_name = f"{uuid.uuid4()}{_EXT[detected]}"
    if is_s3_configured():
        key = f"{S3_PUBLIC_PREFIX if public else S3_PRIVATE_PREFIX}{safe_name}"
        _put_object(key, content, detected)
        if public and settings.s3_public_base_url:
            return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
        # Private files never get a public URL: they are read back with our credentials through
        # the signed-in file endpoints (read_admin_file, read_private_file)
        return f"s3://{settings.s3_bucket}/{key}"

    folder = "public" if public else "private"
    dest = UPLOAD_ROOT / folder / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return f"/uploads/public/{safe_name}" if public else f"private/{safe_name}"


SAFE_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
                    ".pdf": "application/pdf"}


def safe_file_headers(content_type: str, *, filename: str = "document") -> dict[str, str]:
    """Headers for serving an uploaded file: never sniffed, never run as a page, non-images downloaded."""
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; sandbox",
        "Cache-Control": "private, no-store",
    }
    if content_type not in IMAGE_TYPES:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return headers


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


def _read_s3(key: str, prefixes: tuple[str, ...]) -> tuple[bytes, str] | None:
    """Bytes and type of an s3://<our bucket>/<key> object under one of `prefixes`, or None."""
    if not key.startswith("s3://") or not is_s3_configured():
        return None
    bucket, _, obj = key.removeprefix("s3://").partition("/")
    if bucket != settings.s3_bucket or not obj.startswith(prefixes) or ".." in obj.split("/"):
        return None
    try:
        body = _client().get_object(Bucket=bucket, Key=obj)["Body"].read()
    except Exception:
        return None
    return body, sniff_type(body) or "application/octet-stream"


def read_admin_file(key: str) -> tuple[bytes, str, str] | None:
    """
    An ID document or licence copy for the admin file endpoint: (bytes, type, filename), or None.
    Local 'private/<name>' files and private S3 objects only; vetting files are never served here.
    """
    if key.startswith("s3://"):
        found = _read_s3(key, (S3_PRIVATE_PREFIX,))
        if not found:
            return None
        return found[0], found[1], key.rsplit("/", 1)[-1]
    path = private_file_path(key)
    if not path:
        return None
    # The type comes from an allowlist, never from whatever extension was stored; anything else downloads
    return path.read_bytes(), SAFE_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"), path.name


# ---------------------------------------------------------------- vetting documents

# Vetting files (police clearance, certificates) live outside uploads/private so the generic
# admin file endpoint can't serve them: they are only read through the logged document endpoint.
VETTING_ROOT = UPLOAD_ROOT / "vetting"
VETTING_MAX_BYTES = 5 * 1024 * 1024


def sniff_type(content: bytes) -> str | None:
    """The real file type from its first bytes, whatever the name or the browser claims."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def save_vetting_file(content: bytes, *, images_only: bool = False) -> tuple[str, str]:
    """Check and store a vetting document privately. Returns (key, content_type)."""
    if not content:
        raise ValueError("The file is empty")
    if len(content) > VETTING_MAX_BYTES:
        raise ValueError(f"Files must be {VETTING_MAX_BYTES // (1024 * 1024)} MB or smaller")
    kind = sniff_type(content)
    allowed = IMAGE_TYPES if images_only else ALLOWED_UPLOAD_TYPES
    if kind not in allowed:
        raise ValueError("Upload a JPG, PNG or WEBP photo" if images_only
                         else "Upload a JPG, PNG or WEBP photo, or a PDF")
    name = f"{uuid.uuid4()}{_EXT[kind]}"
    if is_s3_configured():
        key = f"{S3_VETTING_PREFIX}{name}"
        _put_object(key, content, kind)
        return f"s3://{settings.s3_bucket}/{key}", kind
    VETTING_ROOT.mkdir(parents=True, exist_ok=True)
    (VETTING_ROOT / name).write_bytes(content)
    return f"vetting/{name}", kind


def read_private_file(key: str) -> tuple[bytes, str] | None:
    """Bytes and type of a private document (vetting files, older ID and licence copies), or None."""
    if key.startswith("vetting/"):
        base = VETTING_ROOT.resolve()
        path = (UPLOAD_ROOT / key).resolve()
        if base not in path.parents or not path.is_file():
            return None
    elif key.startswith("private/"):
        path = private_file_path(key)
        if not path:
            return None
    elif key.startswith("s3://"):
        return _read_s3(key, (S3_VETTING_PREFIX, S3_PRIVATE_PREFIX))
    else:
        return None
    content = path.read_bytes()
    return content, sniff_type(content) or "application/octet-stream"


def delete_vetting_file(key: str | None) -> None:
    """Only used to undo a store when saving the record failed; kept documents are never deleted."""
    if not key or not key.startswith("vetting/"):
        return
    base = VETTING_ROOT.resolve()
    path = (UPLOAD_ROOT / key).resolve()
    if base in path.parents and path.is_file():
        path.unlink()
