"""Uploads on S3/MinIO: private files are never public and are only read back through signed-in endpoints."""

import io
from unittest.mock import MagicMock

import pytest

from config.config import settings
from services import storage_service

API = "/api/v1"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF = b"%PDF-1.4 test"


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setattr(settings, "s3_bucket", "test-bucket")
    monkeypatch.setattr(settings, "aws_access_key_id", "test-key")
    monkeypatch.setattr(settings, "aws_secret_access_key", "test-secret")
    monkeypatch.setattr(settings, "s3_public_base_url", "https://cdn.example.com")
    client = MagicMock()
    objects: dict[str, bytes] = {}
    client.put_object.side_effect = lambda **kw: objects.__setitem__(kw["Key"], kw["Body"])
    client.get_object.side_effect = lambda Bucket, Key: {"Body": io.BytesIO(objects[Key])}
    monkeypatch.setattr(storage_service, "_client", lambda: client)
    client.objects = objects
    return client


def test_private_upload_has_no_acl_and_no_public_url(s3):
    url = storage_service.save_agent_file(PDF, "id.pdf", "application/pdf", public=False)
    assert url.startswith("s3://test-bucket/guday/private/")
    assert "cdn.example.com" not in url
    kwargs = s3.put_object.call_args.kwargs
    assert "ACL" not in kwargs
    assert kwargs["Key"].startswith("guday/private/") and kwargs["ContentType"] == "application/pdf"


def test_public_photo_keeps_its_public_url(s3):
    url = storage_service.save_agent_file(PNG, "me.png", "image/png", public=True)
    assert url.startswith("https://cdn.example.com/guday/public/")
    assert "ACL" not in s3.put_object.call_args.kwargs


def test_vetting_upload_is_private(s3):
    key, kind = storage_service.save_vetting_file(PDF)
    assert key.startswith("s3://test-bucket/vetting/") and kind == "application/pdf"
    assert "ACL" not in s3.put_object.call_args.kwargs
    assert storage_service.read_private_file(key) == (PDF, "application/pdf")


def test_admin_file_reads_private_objects_only(s3):
    key = storage_service.save_agent_file(PDF, "id.pdf", "application/pdf", public=False)
    content, media_type, _ = storage_service.read_admin_file(key)
    assert content == PDF and media_type == "application/pdf"
    vetting_key, _ = storage_service.save_vetting_file(PDF)
    # Police clearances only go through the logged vetting endpoint
    assert storage_service.read_admin_file(vetting_key) is None
    assert storage_service.read_admin_file("s3://other-bucket/guday/private/x.pdf") is None
    assert storage_service.read_admin_file("s3://test-bucket/guday/private/../../vetting/x.pdf") is None
    assert storage_service.read_private_file("s3://test-bucket/references/x.pdf") is None


def test_admin_file_endpoint_serves_s3_private_files_to_staff_only(client, make_staff, make_user, s3):
    key = storage_service.save_agent_file(PDF, "id.pdf", "application/pdf", public=False)
    assert client.get(f"{API}/admin/files", params={"key": key}).status_code == 401
    user = make_user()
    assert client.get(f"{API}/admin/files", params={"key": key}, headers=user["headers"]).status_code in (401, 403)
    r = client.get(f"{API}/admin/files", params={"key": key}, headers=make_staff()["headers"])
    assert r.status_code == 200, r.text
    assert r.content == PDF
    assert r.headers["cache-control"] == "private, no-store"
