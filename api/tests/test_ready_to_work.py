"""Ready to work: a provider is listed and can take new work only while every rule holds (approved listing,
vetting complete including the guarantor, current legal documents, complete profile)."""

import dataclasses
import json

import pytest
from conftest import API
from test_hires_admin import _open_request, _staff
from test_providers import (
    _VETTING_FILES,
    _admin,
    _approved,
    _hire,
    _job,
    _join,
    _pay,
    _vet,
)
from test_vetting import GUARANTOR, _upload

from services import legal, platform_settings, vetting
from services import provider_service as svc
from services.db import execute, fetch_all, fetch_one


@pytest.fixture(autouse=True)
def _track_files():
    """Uploaded test files are deleted when the run ends (tests/test_providers.py)."""
    yield
    _VETTING_FILES.extend(r["file_key"] for r in fetch_all(
        "select file_key from provider_documents where uploaded_by like 'test-%%@example.com' or uploaded_by = 'test'"))


def _listed(client, provider) -> bool:
    return client.get(f"{API}/providers/{provider['slug']}").status_code == 200


def _reasons(pid) -> list[str]:
    return [r["key"] for r in svc.get(pid)["not_ready_reasons"]]


def _guarantor_item(client, user):
    v = client.get(f"{API}/providers/me/vetting", headers=user["headers"]).json()["payload"]["vetting"]
    return next(i for i in v["items"] if i["key"] == "guarantor")


@pytest.fixture
def keep_settings():
    """Snapshot the platform settings and put them back (tests share the app's database)."""
    saved = fetch_all("select key, value, updated_by, updated_at from platform_settings")
    yield
    execute("delete from platform_settings")
    for row in saved:
        execute("insert into platform_settings (key, value, updated_by, updated_at) values (%s, %s, %s, %s)",
                (row["key"], json.dumps(row["value"]), row["updated_by"], row["updated_at"]))
    execute("delete from platform_settings_history where changed_by like 'test%%'")
    platform_settings.clear_cache()
    svc.refresh_readiness_all()


def test_listed_only_while_profile_vetting_and_listing_hold(client, make_user):
    admin, agent = make_user("admin"), make_user()
    p = svc.get(_approved(client, admin, agent)["id"])
    assert p["ready_to_work"] and _listed(client, p)

    # Profile: clearing the About text hides them, with the reason, until it is back
    execute("update providers set bio = null where id = %s", (p["id"],))
    svc.refresh_readiness(p["id"])
    assert not _listed(client, p) and "profile:bio" in _reasons(p["id"])
    mine = client.get(f"{API}/providers/me", headers=agent["headers"]).json()["payload"]["provider"]
    assert mine["readiness"]["listed"] is False
    assert any(r["fix"] == "profile" for r in mine["readiness"]["reasons"])
    assert client.patch(f"{API}/providers/me", json={"bio": "Passports and ID renewals in Bole, done the same week."},
                        headers=agent["headers"]).status_code == 200
    assert _listed(client, p)

    # Vetting holds all the time, not only on approval day: an expired clearance hides them at once
    execute("update provider_documents set status = 'expired' where provider_id = %s and kind = 'police_clearance' "
            "and status = 'verified'", (p["id"],))
    svc.refresh_readiness(p["id"])
    assert not _listed(client, p) and "vetting:police_clearance" in _reasons(p["id"])
    execute("update provider_documents set status = 'verified' where provider_id = %s and kind = 'police_clearance' "
            "and status = 'expired'", (p["id"],))
    svc.refresh_readiness(p["id"])
    assert _listed(client, p)

    # A document that ran out today counts even before the daily run (ready_until)
    execute("update providers set ready_until = current_date - 1 where id = %s", (p["id"],))
    assert not _listed(client, p)
    svc.refresh_readiness(p["id"])
    assert _listed(client, p)

    # Staff list: a filter and the reasons
    execute("update providers set telegram_username = null where id = %s", (p["id"],))
    svc.refresh_readiness(p["id"])
    rows = client.get(f"{API}/admin/marketplace/providers", params={"ready": "false", "q": p["registration_no"]},
                      headers=admin["headers"]).json()["payload"]["items"]
    assert rows and rows[0]["id"] == p["id"] and rows[0]["ready_to_work"] is False
    assert any(r["key"] == "profile:telegram_username" for r in rows[0]["not_ready_reasons"])


def test_new_agreement_version_hides_until_accepted(client, make_user, monkeypatch):
    admin, agent = make_user("admin"), make_user()
    p = _approved(client, admin, agent)
    assert _listed(client, p)
    newer = dataclasses.replace(legal.DOCUMENTS["provider_agreement"], version="9.9-test")
    monkeypatch.setitem(legal.DOCUMENTS, "provider_agreement", newer)
    # A new version ships with a release: the startup check (or the daily run) sees it
    svc.refresh_readiness_all(only=[p["id"]])
    assert not _listed(client, p) and "agreement:provider_agreement" in _reasons(p["id"])
    r = client.post(f"{API}/legal/accept", json={"accept": {"provider_agreement": "9.9-test"}}, headers=agent["headers"])
    assert r.status_code == 200, r.text
    assert _listed(client, p)


def test_approval_needs_profile_and_agreement(client, make_user):
    admin, agent = make_user("admin"), make_user()
    p = _join(client, agent).json()["payload"]["provider"]
    _vet(p["id"])
    execute("update providers set bio = 'short' where id = %s", (p["id"],))
    blocked = _admin(client, admin, p["id"], "approve", vet=False)
    assert blocked.status_code == 409 and "About" in blocked.json()["detail"]


def test_not_ready_cannot_be_hired_assigned_or_take_new_work_but_can_finish(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    p = svc.get(_approved(client, admin, agent)["id"])
    started = _hire(client, customer, p)
    assert _job(client, agent, started["id"], "accept").status_code == 200
    assert _job(client, agent, started["id"], "start").status_code == 200
    waiting = _hire(client, customer, p)
    accepted = _hire(client, customer, p)
    assert _job(client, agent, accepted["id"], "accept").status_code == 200

    # The guarantor's check fails: they are hidden
    g = _guarantor_item(client, agent)["guarantor"]
    assert client.post(f"{API}/admin/marketplace/providers/{p['id']}/guarantor/{g['id']}",
                       json={"decision": "failed", "note": "Number belongs to someone else"},
                       headers=admin["headers"]).status_code == 200
    assert not _listed(client, p)

    r = client.post(f"{API}/hires", json={"provider_id": p["slug"], "title": "Renew my passport",
                                          "client_name": "Test Client", "client_phone": "0922000000"},
                    headers=customer["headers"])
    assert r.status_code == 409 and "can't take new requests" in r.json()["detail"]
    assert "Guarantor" not in r.json()["detail"]  # the client never learns why

    open_req = _open_request(client, customer)
    cands = client.get(f"{API}/admin/marketplace/engagements/{open_req['id']}/candidates", params={"q": p["registration_no"]},
                       headers=admin["headers"]).json()["payload"]
    assert cands["total"] == 0
    r = _staff(client, admin, open_req["id"], "assign", provider_id=p["id"])
    assert r.status_code == 409 and "Guarantor" in r.json()["detail"]

    r = _job(client, agent, waiting["id"], "accept")
    assert r.status_code == 409 and "Guarantor" in r.json()["detail"]
    assert _job(client, agent, accepted["id"], "start").status_code == 409
    assert _job(client, agent, waiting["id"], "decline", reason="Not able right now").status_code == 200
    # Work already started is still delivered and paid for
    _job(client, agent, started["id"], "complete", note="Passport renewed and collected from the Bole office.")
    assert svc.get_engagement(started["id"])["status"] == "completed"
    _pay(client, customer, started["id"])
    assert svc.get_engagement(started["id"])["payment_status"] == "paid"


def test_guarantor_flow_enter_confirm_replace(client, make_user):
    admin, agent = make_user("admin"), make_user()
    p = _approved(client, admin, agent)
    item = _guarantor_item(client, agent)
    assert item["status"] == "verified" and item["required"]
    assert "checked_by" not in item["guarantor"] and "note" not in item["guarantor"]

    # Consent, own phone and own name are refused
    bad = client.put(f"{API}/providers/me/guarantor", json={**GUARANTOR, "consent": False}, headers=agent["headers"])
    assert bad.status_code == 400 and "agreed" in bad.json()["detail"]
    assert client.put(f"{API}/providers/me/guarantor", json={**GUARANTOR, "phone": "0911000000"},
                      headers=agent["headers"]).status_code == 400
    assert client.put(f"{API}/providers/me/guarantor", json={**GUARANTOR, "full_name": "Test Agent"},
                      headers=agent["headers"]).status_code == 400

    # A new person replaces the old one: back to pending, hidden, old record and papers kept as superseded
    old = item["guarantor"]
    r = client.put(f"{API}/providers/me/guarantor", json=GUARANTOR, headers=agent["headers"])
    assert r.status_code == 200, r.text
    new = next(i for i in r.json()["payload"]["vetting"]["items"] if i["key"] == "guarantor")
    assert new["status"] == "missing" and new["guarantor"]["id_last4"] == "4444"
    assert not _listed(client, p)
    stored = fetch_one("select id_number_enc, status from provider_guarantors where id = %s", (new["guarantor"]["id"],))
    assert "1111" not in stored["id_number_enc"] and stored["status"] == "pending"
    assert fetch_one("select status from provider_guarantors where id = %s", (old["id"],))["status"] == "superseded"
    assert {r["status"] for r in fetch_all("select status from provider_documents where provider_id = %s and "
                                           "kind in ('guarantee_letter', 'guarantor_id') and guarantor_id = %s",
                                           (p["id"], old["id"]))} == {"superseded"}

    # Staff see the details, how to verify, the replaced one; a confirmation needs a real note
    detail = client.get(f"{API}/admin/marketplace/providers/{p['id']}", headers=admin["headers"]).json()["payload"]["provider"]
    staff_item = next(i for i in detail["vetting"]["items"] if i["key"] == "guarantor")
    assert staff_item["how_to_verify"] and staff_item["history"][0]["id"] == old["id"]
    assert all(d.get("how_to_verify") for d in staff_item["documents"])
    assert "id_number_enc" not in json.dumps(detail)
    assert any(r["key"] == "vetting:guarantor" for r in detail["readiness"]["reasons"])
    gid = new["guarantor"]["id"]
    assert client.post(f"{API}/admin/marketplace/providers/{p['id']}/guarantor/{gid}", json={"decision": "confirmed", "note": "ok"},
                       headers=admin["headers"]).status_code == 400
    assert client.post(f"{API}/admin/marketplace/providers/{p['id']}/guarantor/{old['id']}",
                       json={"decision": "confirmed", "note": "Called, she confirmed"}, headers=admin["headers"]).status_code == 404

    # Papers, then the call: listed again
    letter = None
    for kind in ("guarantee_letter", "guarantor_id"):
        doc = _upload(client, agent, kind).json()["payload"]["document"]
        letter = letter or doc
        assert client.post(f"{API}/admin/marketplace/providers/{p['id']}/documents/{doc['id']}/review",
                           json={"decision": "verified"}, headers=admin["headers"]).status_code == 200
    assert not _listed(client, p)  # papers alone are not enough
    assert client.post(f"{API}/admin/marketplace/providers/{p['id']}/guarantor/{gid}",
                       json={"decision": "confirmed", "note": "Called her, she signed it knowingly"},
                       headers=admin["headers"]).status_code == 200
    assert _listed(client, p)

    # Opening a guarantor's paper is logged
    assert client.get(f"{API}/admin/marketplace/providers/{p['id']}/documents/{letter['id']}/file",
                      headers=admin["headers"]).status_code == 200
    assert fetch_one("select 1 from provider_events where provider_id = %s and action = 'document_viewed'", (p["id"],))

    # Correcting the same person's details keeps the papers but needs a new call
    r = client.put(f"{API}/providers/me/guarantor", json={**GUARANTOR, "woreda": "07"}, headers=agent["headers"])
    same = next(i for i in r.json()["payload"]["vetting"]["items"] if i["key"] == "guarantor")
    assert same["guarantor"]["id"] == gid and same["status"] == "pending"
    assert all(d["status"] == "verified" for d in same["documents"] if d["required"])
    assert not _listed(client, p)


def test_guarantor_setting_change_rechecks_everyone(client, make_user, keep_settings):
    admin, agent = make_user("admin"), make_user()
    p = _approved(client, admin, agent)
    g = _guarantor_item(client, agent)["guarantor"]
    client.post(f"{API}/admin/marketplace/providers/{p['id']}/guarantor/{g['id']}",
                json={"decision": "failed", "note": "Did not answer three times"}, headers=admin["headers"])
    assert not _listed(client, p)
    platform_settings.update({"vetting_guarantor_required": False}, "test")
    assert _listed(client, p)  # no guarantor needed any more
    platform_settings.update({"vetting_guarantor_required": True}, "test")
    assert not _listed(client, p)
    # Join page lists the guarantor as a requirement
    tpl = client.get(f"{API}/providers/vetting-requirements").json()["payload"]["vetting"]
    g_item = next(i for i in tpl["items"] if i["key"] == "guarantor")
    assert g_item["required"] and {d["kind"] for d in g_item["documents"]} >= {"guarantee_letter", "guarantor_id"}
    # Companies: off by default
    tpl = client.get(f"{API}/providers/vetting-requirements", params={"entity": "company"}).json()["payload"]["vetting"]
    assert not any(i["key"] == "guarantor" for i in tpl["items"])
    assert vetting.guarantor_required({"entity_type": "company"}) is False


def test_daily_run_rechecks_readiness(client, make_user):
    admin, agent = make_user("admin"), make_user()
    p = _approved(client, admin, agent)
    execute("update providers set ready_to_work = false where id = %s", (p["id"],))
    assert not _listed(client, p)
    vetting.run_daily(only=[p["id"]])
    assert _listed(client, p)
