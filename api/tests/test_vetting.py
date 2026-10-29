"""Vetting: documents a provider hands in, staff checks, and what they unlock."""

from datetime import date, timedelta

import pytest
from conftest import API
from test_providers import _VETTING_FILES, PNG, _admin, _join, _vet

from services import platform_settings, vetting
from services.db import execute, fetch_all, fetch_one

PDF = b"%PDF-1.4\n%fake test pdf\n"
HTML = b"<html><script>fetch('/api/v1/auth/refresh',{method:'POST'})</script></html>"
TODAY = date.today()


@pytest.fixture(autouse=True)
def _track_files():
    yield
    _VETTING_FILES.extend(r["file_key"] for r in fetch_all(
        "select d.file_key from provider_documents d join providers p on p.id = d.provider_id "
        "where d.uploaded_by like 'test-%%@example.com' or d.uploaded_by = 'test'"))


def _provider(client, user, **overrides) -> dict:
    r = _join(client, user, **overrides)
    assert r.status_code == 201, r.text
    return r.json()["payload"]["provider"]


def _upload(client, user, kind, content=PNG, name="doc.png", ctype="image/png", **fields):
    data = {"kind": kind, **{k: str(v) for k, v in fields.items()}}
    return client.post(f"{API}/providers/me/documents", data=data, files={"file": (name, content, ctype)},
                       headers=user["headers"])


def _clearance(client, user, days_old=10, consent=True, **extra):
    if consent:
        extra["consent"] = "true"
    return _upload(client, user, "police_clearance", issued_on=TODAY - timedelta(days=days_old),
                   reference_no="FPC/123/2026", **extra)


def _decide(client, admin, pid, doc_id, decision, **body):
    return client.post(f"{API}/admin/marketplace/providers/{pid}/documents/{doc_id}/review",
                       json={"decision": decision, **body}, headers=admin["headers"])


def _item(client, user, key):
    v = client.get(f"{API}/providers/me/vetting", headers=user["headers"]).json()["payload"]["vetting"]
    return next(i for i in v["items"] if i["key"] == key)


GUARANTOR = {"full_name": "Almaz Tesfaye", "phone": "0944112233", "relationship": "Former employer",
             "sub_city": "Kirkos", "woreda": "05", "occupation": "Bank cashier", "employer": "Test Bank",
             "id_number": "1111 2222 3333 4444", "consent": True}


def _add_verified_guarantor(client, admin, user, pid, **overrides):
    """Provider enters the guarantor and uploads the letter and ID; staff verify both and confirm by phone."""
    r = client.put(f"{API}/providers/me/guarantor", json={**GUARANTOR, **overrides}, headers=user["headers"])
    assert r.status_code == 200, r.text
    item = next(i for i in r.json()["payload"]["vetting"]["items"] if i["key"] == "guarantor")
    for kind in ("guarantee_letter", "guarantor_id"):
        doc = _upload(client, user, kind, reference_no="DARS-77").json()["payload"]["document"]
        assert _decide(client, admin, pid, doc["id"], "verified", note="DARS stamp checked").status_code == 200
    r = client.post(f"{API}/admin/marketplace/providers/{pid}/guarantor/{item['guarantor']['id']}",
                    json={"decision": "confirmed", "note": "Called her, she signed it knowingly"}, headers=admin["headers"])
    assert r.status_code == 200, r.text
    return item["guarantor"]


def test_upload_checks_the_real_file_type_size_and_dates(client, make_user):
    user = make_user()
    _provider(client, user)
    # An HTML page dressed up as a PDF, or a JPG name on random bytes, is refused
    assert _clearance(client, user, content=HTML, name="c.pdf", ctype="application/pdf").status_code == 400
    assert _upload(client, user, "education", content=b"not an image", name="a.jpg", ctype="image/jpeg",
                   level="grade_12").status_code == 400
    too_big = _clearance(client, user, content=PNG + b"0" * (5 * 1024 * 1024))
    assert too_big.status_code == 400 and "MB" in too_big.json()["detail"]
    # Police clearance needs explicit consent, its date and number, and can't be older than the setting allows
    no_consent = _clearance(client, user, consent=False)
    assert no_consent.status_code == 400 and "agree" in no_consent.json()["detail"]
    assert _upload(client, user, "police_clearance", reference_no="X1", consent="true").status_code == 400
    old = _clearance(client, user, days_old=platform_settings.get_int("police_clearance_max_age_days") + 5)
    assert old.status_code == 400 and "days old" in old.json()["detail"]
    assert _clearance(client, user, days_old=-3).status_code == 400  # issued in the future
    # Education below the minimum, and a photo that is a PDF
    assert _upload(client, user, "education", level="grade_10").status_code == 400
    assert _upload(client, user, "photo", content=PDF, name="p.pdf", ctype="application/pdf").status_code == 400
    # Companies' documents aren't part of an individual's checklist
    assert _upload(client, user, "trade_licence", reference_no="AA/1", expires_on=TODAY + timedelta(days=90)).status_code == 400

    ok = _clearance(client, user, content=PDF, name="clearance.exe", ctype="application/pdf")
    assert ok.status_code == 201, ok.text
    doc = ok.json()["payload"]["document"]
    assert doc["status"] == "pending" and doc["content_type"] == "application/pdf" and "file_key" not in doc
    assert doc["consent_at"]  # when they agreed is kept with the document
    assert fetch_one("select file_key from provider_documents where id = %s", (doc["id"],))["file_key"].endswith(".pdf")


def test_verify_and_reject_each_document(client, make_user):
    admin, user = make_user("admin"), make_user()
    p = _provider(client, user)
    first = _clearance(client, user).json()["payload"]["document"]
    # A rejection always says why, and the provider sees it
    assert _decide(client, admin, p["id"], first["id"], "rejected").status_code == 400
    assert _decide(client, admin, p["id"], first["id"], "rejected", note="Stamp is not readable").status_code == 200
    item = _item(client, user, "police_clearance")
    assert item["status"] == "rejected" and "Stamp is not readable" in item["message"]
    assert _decide(client, admin, p["id"], first["id"], "verified").status_code == 409  # only pending

    second = _clearance(client, user, days_old=5).json()["payload"]["document"]
    r = _decide(client, admin, p["id"], second["id"], "verified", reference_no="FPC/999/2026")
    assert r.status_code == 200, r.text
    item = _item(client, user, "police_clearance")
    assert item["status"] == "verified" and item["current"]["reference_no"] == "FPC/999/2026"
    # History keeps everything: the rejected copy is still on file (replaced), with its reason
    hist = client.get(f"{API}/admin/marketplace/providers/{p['id']}/documents", headers=admin["headers"]).json()["payload"]
    assert hist["total"] == 2 and {d["status"] for d in hist["items"]} == {"verified", "superseded"}
    assert any(d["review_note"] == "Stamp is not readable" for d in hist["items"])

    # A new upload doesn't knock out the verified one until it is checked itself
    third = _clearance(client, user, days_old=1).json()["payload"]["document"]
    assert _item(client, user, "police_clearance")["status"] == "verified"
    assert _decide(client, admin, p["id"], third["id"], "verified").status_code == 200
    statuses = {r["id"]: r["status"] for r in fetch_all(
        "select id::text, status from provider_documents where provider_id = %s", (p["id"],))}
    assert statuses[second["id"]] == "superseded" and statuses[third["id"]] == "verified"
    # Education must be at the required level when staff confirm it
    edu = _upload(client, user, "education", level="grade_12").json()["payload"]["document"]
    assert _decide(client, admin, p["id"], edu["id"], "verified", level="grade_10").status_code == 400
    assert _decide(client, admin, p["id"], edu["id"], "verified").status_code == 200


def test_approval_waits_for_every_required_document(client, make_user):
    admin, user = make_user("admin"), make_user()
    p = _provider(client, user, telegram_username="test_vetting_tg")
    blocked = _admin(client, admin, p["id"], "approve", vet=False)
    assert blocked.status_code == 409 and "Police clearance" in blocked.json()["detail"]
    detail = client.get(f"{API}/admin/marketplace/providers/{p['id']}", headers=admin["headers"]).json()["payload"]["provider"]
    assert detail["vetting"]["complete"] is False
    assert all(i.get("how_to_verify") for i in detail["vetting"]["items"] if i["type"] == "document")

    for kind, extra in (("police_clearance", {"issued_on": TODAY - timedelta(days=3), "reference_no": "FPC-1", "consent": "true"}),
                        ("education", {"level": "diploma"}), ("photo", {})):
        doc = _upload(client, user, kind, **extra).json()["payload"]["document"]
        still = _admin(client, admin, p["id"], "approve", vet=False)
        assert still.status_code == 409  # uploaded is not enough, staff must check it
        assert _decide(client, admin, p["id"], doc["id"], "verified").status_code == 200
    # The guarantor (ተያዥ) is required for individuals by default
    blocked = _admin(client, admin, p["id"], "approve", vet=False)
    assert blocked.status_code == 409 and "Guarantor" in blocked.json()["detail"]
    _add_verified_guarantor(client, admin, user, p["id"])
    # The profile must be complete too: About is missing
    blocked = _admin(client, admin, p["id"], "approve", vet=False)
    assert blocked.status_code == 409 and "About" in blocked.json()["detail"]
    assert client.patch(f"{API}/providers/me", json={"bio": "I handle passport renewals at the Bole office for families."},
                        headers=user["headers"]).status_code == 200
    r = _admin(client, admin, p["id"], "approve", vet=False)
    assert r.status_code == 200, r.text
    score = r.json()["payload"]["provider"]["score_breakdown"]
    verification = next(x for x in score if x["key"] == "verification")
    assert "police clearance" in verification["detail"] and "education" in verification["detail"]


def test_references_when_required(client, make_user):
    admin, user = make_user("admin"), make_user()
    p = _provider(client, user)
    _vet(p["id"])
    before = platform_settings.get("vetting_references_required")
    platform_settings.update({"vetting_references_required": True}, "test")
    try:
        assert _admin(client, admin, p["id"], "approve", vet=False).status_code == 409
        refs = [{"name": "Abebe Tesfaye", "phone": "0911223344", "relationship": "Former employer"},
                {"name": "Sara Bekele", "phone": "0911556677", "relationship": "Kebele chair"}]
        assert client.put(f"{API}/providers/me/references", json={"references": refs + [refs[0]]},
                          headers=user["headers"]).status_code == 400  # same phone twice
        assert client.put(f"{API}/providers/me/references", json={"references": refs},
                          headers=user["headers"]).status_code == 200
        detail = client.get(f"{API}/admin/marketplace/providers/{p['id']}", headers=admin["headers"]).json()["payload"]["provider"]
        ref_ids = [r["id"] for r in next(i for i in detail["vetting"]["items"] if i["key"] == "references")["references"]]
        for rid in ref_ids:
            assert client.post(f"{API}/admin/marketplace/providers/{p['id']}/references/{rid}",
                               json={"decision": "confirmed"}, headers=admin["headers"]).status_code == 200
        assert _admin(client, admin, p["id"], "approve", vet=False).status_code == 200
    finally:
        if before == platform_settings.BY_KEY["vetting_references_required"].default():
            platform_settings.reset("vetting_references_required", "test")
        else:
            platform_settings.update({"vetting_references_required": before}, "test")
        execute("delete from platform_settings_history where changed_by like 'test%%' and key = 'vetting_references_required'")


def test_expired_clearance_blocks_renewal_and_pauses_the_listing(client, make_user):
    admin, user = make_user("admin"), make_user()
    p = _provider(client, user)
    assert _admin(client, admin, p["id"], "approve").status_code == 200
    execute("update providers set license_expires_at = current_date + 10 where id = %s", (p["id"],))
    max_age = platform_settings.get_int("police_clearance_max_age_days")

    # Close to the limit: a reminder, once
    execute("update provider_documents set issued_on = current_date - %s where provider_id = %s and kind = 'police_clearance' "
            "and status = 'verified'", (max_age - 5, p["id"]))
    first = vetting.run_daily(only=[p["id"]])
    assert first["reminders_sent"] == 1 and vetting.run_daily(only=[p["id"]])["reminders_sent"] == 0
    assert fetch_one("select count(*) as n from notifications where user_id = %s and kind = 'vetting'", (user["id"],))["n"] >= 1

    # Past the limit: renewal is refused, and the daily run expires it and pauses the listing
    execute("update provider_documents set issued_on = current_date - %s where provider_id = %s and kind = 'police_clearance' "
            "and status = 'verified'", (max_age + 1, p["id"]))
    renew = _admin(client, admin, p["id"], "renew")
    assert renew.status_code == 409 and "Police clearance" in renew.json()["detail"]
    result = vetting.run_daily(only=[p["id"]])
    assert result == {"documents_expired": 1, "listings_suspended": 1, "reminders_sent": 0}
    row = fetch_one("select status, review_note from providers where id = %s", (p["id"],))
    assert row["status"] == "suspended" and "document expired" in row["review_note"]
    assert client.get(f"{API}/providers/{p['slug']}").status_code == 404
    # Reinstating needs a new clearance first; a document expiry is not a penalty on the score
    assert _admin(client, admin, p["id"], "reinstate").status_code == 409
    assert not fetch_one("select 1 from provider_events where provider_id = %s and action = 'suspend'", (p["id"],))
    doc = _clearance(client, user, days_old=2).json()["payload"]["document"]
    assert _decide(client, admin, p["id"], doc["id"], "verified").status_code == 200
    assert _admin(client, admin, p["id"], "reinstate").status_code == 200


def test_staff_views_of_a_police_clearance_are_logged(client, make_user):
    admin, user = make_user("admin"), make_user()
    p = _provider(client, user)
    clearance = _clearance(client, user, content=PDF, name="c.pdf", ctype="application/pdf").json()["payload"]["document"]
    edu = _upload(client, user, "education", level="grade_12").json()["payload"]["document"]
    base = f"{API}/admin/marketplace/providers/{p['id']}/documents"

    r = client.get(f"{base}/{clearance['id']}/file", headers=admin["headers"])
    assert r.status_code == 200 and r.content == PDF
    # Served so it can never run as a page in the admin's browser
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-content-type-options"] == "nosniff" and "sandbox" in r.headers["content-security-policy"]
    assert r.headers["content-disposition"].startswith("attachment")
    assert client.get(f"{base}/{edu['id']}/file", headers=admin["headers"]).status_code == 200

    events = client.get(f"{API}/admin/marketplace/providers/{p['id']}", headers=admin["headers"]).json()["payload"]["provider"]["events"]
    views = [e for e in events if e["action"] == "document_viewed"]
    assert len(views) == 1 and views[0]["actor"] == admin["email"] and "FPC/123/2026" in views[0]["note"]
    # The provider opening their own copy is not a staff view
    assert client.get(f"{API}/providers/me/documents/{clearance['id']}/file", headers=user["headers"]).status_code == 200
    assert fetch_one("select count(*) as n from provider_events where provider_id = %s and action = 'document_viewed'",
                     (p["id"],))["n"] == 1


def test_providers_cannot_reach_each_others_documents(client, make_user):
    admin, alice, bob = make_user("admin"), make_user(), make_user()
    pa, pb = _provider(client, alice), _provider(client, bob)
    doc = _clearance(client, alice).json()["payload"]["document"]

    assert client.get(f"{API}/providers/me/documents/{doc['id']}/file", headers=bob["headers"]).status_code == 404
    assert all(d["id"] != doc["id"] for d in
               client.get(f"{API}/providers/me/documents", headers=bob["headers"]).json()["payload"]["items"])
    # Bob's upload lands on his own profile only; Alice's pending copy is untouched
    assert _clearance(client, bob).status_code == 201
    assert fetch_one("select status from provider_documents where id = %s", (doc["id"],))["status"] == "pending"
    # Staff routes check the document belongs to the provider in the URL
    assert _decide(client, admin, pb["id"], doc["id"], "verified").status_code == 404
    assert client.get(f"{API}/admin/marketplace/providers/{pb['id']}/documents/{doc['id']}/file",
                      headers=admin["headers"]).status_code == 404
    # Non-staff can't use the staff routes at all
    assert _decide(client, bob, pa["id"], doc["id"], "verified").status_code in (401, 403)
    assert client.get(f"{API}/admin/marketplace/providers/{pa['id']}/documents/{doc['id']}/file",
                      headers=bob["headers"]).status_code in (401, 403)
    # Someone without a provider profile has no documents
    assert client.get(f"{API}/providers/me/vetting", headers=make_user()["headers"]).status_code == 404


def test_uploads_are_typed_by_their_bytes_and_served_safely(client, make_user):
    from pathlib import Path

    user, admin = make_user(), make_user("admin")
    # The join form's licence copy and the profile photo are sniffed too
    company = _join(client, user, provider_type="agency", entity_type="company", display_name="Test Vetting PLC",
                    specialties=["customs_clearing"], legal_name="Test Vetting PLC", tin="0012345678",
                    trade_license_no="AA/14/9", files={"license_document": ("lic.pdf", HTML, "application/pdf")})
    assert company.status_code == 400
    _provider(client, user)
    bad = client.post(f"{API}/providers/me/photo", files={"photo": ("me.html", HTML, "image/png")}, headers=user["headers"])
    assert bad.status_code == 400
    liar = client.post(f"{API}/providers/me/photo", files={"photo": ("me.png", b"\xff\xd8\xff" + b"0" * 20, "image/png")},
                       headers=user["headers"])
    assert liar.status_code == 400  # JPEG bytes declared as PNG
    ok = client.post(f"{API}/providers/me/photo", files={"photo": ("me.html", PNG, "image/png")}, headers=user["headers"])
    assert ok.status_code == 200, ok.text
    url = ok.json()["payload"]["photo_url"]
    assert url.endswith(".png")  # the stored extension follows the bytes, not the name
    served = client.get(url)
    assert served.status_code == 200 and served.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in served.headers["content-security-policy"]
    client.delete(f"{API}/providers/me/photo", headers=user["headers"])

    # The generic staff file route sets the same headers
    key = "private/test-vetting-headers.pdf"
    Path("uploads/private").mkdir(parents=True, exist_ok=True)
    Path("uploads", key).write_bytes(PDF)
    try:
        r = client.get(f"{API}/admin/files", params={"key": key}, headers=admin["headers"])
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["content-disposition"].startswith("attachment")
    finally:
        Path("uploads", key).unlink(missing_ok=True)


def test_trust_score_weights_still_add_up():
    from services import trust_score

    base = dict(review_count=0, review_sum=0, fayda_verified=True, has_phone=True, has_tin=True,
                has_trade_license=True, external_license_verified=True, completed=0, failed=0,
                approved_at=None, upheld_disputes=0, suspensions=0, police_clearance_verified=True,
                education_verified=True)
    for entity in ("individual", "company"):
        parts = trust_score.compute({**base, "entity_type": entity})["parts"]
        assert next(p for p in parts if p["key"] == "verification")["points"] == 25
    assert sum(p["max"] for p in trust_score.compute({**base, "entity_type": "individual"})["parts"]) == 100


def test_approved_providers_name_tin_and_vat_changes_wait_for_staff(client, make_user):
    admin, user = make_user("admin"), make_user()
    p = _provider(client, user)
    assert _admin(client, admin, p["id"], "approve").status_code == 200
    r = client.patch(f"{API}/providers/me", json={"tin": "0098765432", "vat_registered": True, "vat_number": "VAT-777",
                                                   "headline": "Passport help in Bole"}, headers=user["headers"])
    assert r.status_code == 200, r.text
    me = r.json()["payload"]["provider"]
    # The headline changes at once; TIN and VAT stay as they were until staff check them
    assert me["headline"] == "Passport help in Bole" and me["tin"] is None and me["vat_registered"] is False
    assert me["pending_change"]["changes"] == {"tin": "0098765432", "vat_registered": True, "vat_number": "VAT-777"}
    # Editing again adds to the same request
    client.patch(f"{API}/providers/me", json={"tin": "0011112222"}, headers=user["headers"])
    detail = client.get(f"{API}/admin/marketplace/providers/{p['id']}", headers=admin["headers"]).json()["payload"]["provider"]
    change = detail["pending_change"]
    assert change["changes"]["tin"] == "0011112222" and change["old_values"]["tin"] is None
    url = f"{API}/admin/marketplace/providers/{p['id']}/changes/{change['id']}"
    assert client.post(url, json={"decision": "reject"}, headers=admin["headers"]).status_code == 400  # reason needed
    assert client.post(url, json={"decision": "reject", "note": "VAT number not on the certificate"},
                       headers=admin["headers"]).status_code == 200
    me = client.get(f"{API}/providers/me", headers=user["headers"]).json()["payload"]["provider"]
    assert me["vat_registered"] is False and me["pending_change"] is None
    assert "not on the certificate" in me["rejected_change"]["note"]

    client.patch(f"{API}/providers/me", json={"vat_registered": True, "vat_number": "VAT-888"}, headers=user["headers"])
    change = client.get(f"{API}/admin/marketplace/providers/{p['id']}", headers=admin["headers"]).json()["payload"]["provider"]["pending_change"]
    assert client.post(f"{API}/admin/marketplace/providers/{p['id']}/changes/{change['id']}",
                       json={"decision": "approve", "note": "Checked the VAT certificate"}, headers=admin["headers"]).status_code == 200
    me = client.get(f"{API}/providers/me", headers=user["headers"]).json()["payload"]["provider"]
    assert me["vat_registered"] is True and me["vat_number"] == "VAT-888"
    # A provider still under review edits directly
    other = make_user()
    _provider(client, other)
    r = client.patch(f"{API}/providers/me", json={"tin": "0012345678"}, headers=other["headers"])
    assert r.json()["payload"]["provider"]["tin"] == "0012345678"
