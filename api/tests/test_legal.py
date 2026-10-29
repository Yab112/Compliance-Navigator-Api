"""Legal documents: agreeing at sign-up, accepting new versions, and the provider agreement."""

import re
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from auth import service as auth_service
from auth.service import ClientInfo
from conftest import API, LEGAL_ACCEPT
from services import legal, user_store
from services.db import execute, fetch_all, fetch_one

WEB_CONTENT = Path(__file__).resolve().parents[2] / "web" / "src" / "content" / "legal"


@pytest.fixture
def registered(client):
    """Registers through the API and removes every account (and its agreements) afterwards."""
    emails: list[str] = []

    def _register(**extra):
        email = f"test-{uuid.uuid4().hex[:10]}@example.com"
        emails.append(email)
        body = {"email": email, "password": "good-pass-1", "fullname": "Legal Test", **extra}
        return email, client.post(f"{API}/auth/register", json=body)

    yield _register
    for email in emails:
        execute("delete from user_consents where user_id in (select id from users where email = %s)", (email,))
        execute("delete from users where email = %s", (email,))


def _user_exists(email: str) -> bool:
    return fetch_one("select 1 as x from users where email = %s", (email,)) is not None


def test_register_without_consent_is_refused(registered):
    email, r = registered()
    assert r.status_code == 400
    assert "Terms of Service" in r.json()["detail"]
    assert not _user_exists(email)


def test_register_with_a_box_unticked_is_refused(registered):
    partial = {k: v for k, v in LEGAL_ACCEPT.items() if k != "marketplace_rules"}
    email, r = registered(accept=partial)
    assert r.status_code == 400
    assert "Marketplace Rules" in r.json()["detail"]
    assert not _user_exists(email)


def test_register_with_an_old_version_is_refused(registered):
    email, r = registered(accept={**LEGAL_ACCEPT, "terms": "0.9"})
    assert r.status_code == 400
    assert "changed" in r.json()["detail"]
    assert not _user_exists(email)


def test_register_with_unknown_document_is_refused(registered):
    email, r = registered(accept={**LEGAL_ACCEPT, "something_else": "1.0"})
    assert r.status_code == 400
    assert not _user_exists(email)


def test_register_records_consents_with_ip(registered):
    email, r = registered(accept=LEGAL_ACCEPT)
    assert r.status_code == 201, r.text
    user_id = fetch_one("select id::text from users where email = %s", (email,))["id"]
    rows = fetch_all("select document, version, ip, user_agent from user_consents where user_id = %s", (user_id,))
    assert {row["document"]: row["version"] for row in rows} == LEGAL_ACCEPT
    assert all(row["ip"] == "testclient" and row["user_agent"] for row in rows)


def test_account_and_consents_are_one_transaction():
    """If saving the agreements fails, the account must not be created either."""
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"

    def boom(conn, user):
        raise RuntimeError("consent insert failed")

    with pytest.raises(RuntimeError):
        auth_service.register(email, "good-pass-1", "Rollback", None, ClientInfo(ip="testclient"), on_created=boom)
    assert not _user_exists(email)


def test_status_and_accepting_a_new_version(client, make_user, monkeypatch):
    user = make_user()
    r = client.get(f"{API}/legal/status", headers=user["headers"])
    assert r.status_code == 200
    body = r.json()["payload"]
    assert body["upToDate"] and body["pending"] == []
    assert {d["key"] for d in body["documents"]} == set(legal.CLIENT_REQUIRED)

    # We publish new Terms: the person is asked again
    monkeypatch.setitem(legal.DOCUMENTS, "terms", replace(legal.DOCUMENTS["terms"], version="2.0"))
    body = client.get(f"{API}/legal/status", headers=user["headers"]).json()["payload"]
    assert body["pending"] == ["terms"] and not body["upToDate"]

    stale = client.post(f"{API}/legal/accept", json={"accept": {"terms": "1.0"}}, headers=user["headers"])
    assert stale.status_code == 400
    ok = client.post(f"{API}/legal/accept", json={"accept": {"terms": "2.0"}}, headers=user["headers"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["payload"]["upToDate"]
    # Accepting twice is harmless
    assert client.post(f"{API}/legal/accept", json={"accept": {"terms": "2.0"}}, headers=user["headers"]).status_code == 200

    # Both versions stay on record, newest first, paged
    page = client.get(f"{API}/legal/consents?limit=2&offset=0", headers=user["headers"]).json()["payload"]
    assert page["total"] == 4 and len(page["items"]) == 2
    assert page["items"][0]["document"] == "terms" and page["items"][0]["version"] == "2.0"
    old_terms = fetch_one(
        "select 1 as x from user_consents where user_id = %s and document = 'terms' and version = '1.0'", (user["id"],)
    )
    assert old_terms is not None


def test_accept_rejects_empty_and_unknown(client, make_user):
    user = make_user()
    assert client.post(f"{API}/legal/accept", json={"accept": {}}, headers=user["headers"]).status_code == 400
    r = client.post(f"{API}/legal/accept", json={"accept": {"nope": "1.0"}}, headers=user["headers"])
    assert r.status_code == 400


def test_legal_endpoints_need_sign_in(client):
    assert client.get(f"{API}/legal/status").status_code == 401
    assert client.post(f"{API}/legal/accept", json={"accept": LEGAL_ACCEPT}).status_code == 401
    assert client.get(f"{API}/legal/consents").status_code == 401
    docs = client.get(f"{API}/legal/documents").json()["payload"]
    assert docs["clientRequired"] == list(legal.CLIENT_REQUIRED)


def test_provider_agreement(client, make_user, monkeypatch):
    user = make_user()
    with pytest.raises(legal.LegalError) as exc:
        legal.require_accepted(user["id"], ["provider_agreement"])
    assert exc.value.status_code == 400 and "Provider Agreement" in exc.value.detail

    # Once someone is a provider, the agreement joins their required list
    monkeypatch.setattr(legal, "_is_provider", lambda _uid: True)
    body = client.get(f"{API}/legal/status", headers=user["headers"]).json()["payload"]
    assert body["pending"] == ["provider_agreement"]

    version = legal.DOCUMENTS["provider_agreement"].version
    r = client.post(f"{API}/legal/accept", json={"accept": {"provider_agreement": version}}, headers=user["headers"])
    assert r.status_code == 200 and r.json()["payload"]["upToDate"]
    legal.require_accepted(user["id"], ["provider_agreement"])  # no longer raises


def test_deactivating_keeps_consents(make_user):
    user = make_user()
    # The same call the staff "deactivate" action makes
    assert user_store.update_user(user["id"], is_active=False)
    count = fetch_one("select count(*) as n from user_consents where user_id = %s", (user["id"],))["n"]
    assert count == len(LEGAL_ACCEPT)


def test_web_documents_match_the_registry():
    """Version and effective date in web/src/content/legal must match services/legal.py."""
    if not WEB_CONTENT.exists():
        pytest.skip("web app not checked out next to the API")
    found = {}
    for path in WEB_CONTENT.glob("*.ts"):
        text = path.read_text(encoding="utf-8")
        key = re.search(r'\bkey:\s*"([a-z_]+)"', text)
        if not key:
            continue
        version = re.search(r'\bversion:\s*"([^"]+)"', text).group(1)
        effective = re.search(r'\beffective:\s*"([^"]+)"', text).group(1)
        found[key.group(1)] = (version, effective)
    for key, doc in legal.DOCUMENTS.items():
        assert found.get(key) == (doc.version, doc.effective), f"{key}: web has {found.get(key)}"
