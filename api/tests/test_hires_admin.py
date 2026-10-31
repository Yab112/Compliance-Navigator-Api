"""Staff tools for hires: allowed changes only, history, complaints decided once, refunds flagged,
assignment candidates, CSV export, safe sample removal and what the public never sees."""

from conftest import API
from services import provider_service as svc
from services.db import connection, execute, fetch_all, fetch_one
from test_providers import PASSPORT_RENEWAL, _approved, _deliver, _hire, _job, _pay

H = f"{API}/admin/marketplace/engagements"


def _open_request(client, customer) -> dict:
    """A request without a provider: staff find one."""
    r = client.post(f"{API}/hires", json={"service_id": PASSPORT_RENEWAL, "client_name": "Test Client",
                                          "client_phone": "0922000000", "client_telegram": "test_client", "sub_city": "bole"}, headers=customer["headers"])
    assert r.status_code == 201, r.text
    return r.json()["payload"]["hire"]


def _staff(client, admin, hire_id, action, note="Checked with the client by phone", **extra):
    return client.patch(f"{H}/{hire_id}", json={"action": action, "note": note, **extra}, headers=admin["headers"])


def _bell(client, who):
    return client.get(f"{API}/notifications", headers=who["headers"]).json()["payload"]["items"]


def test_staff_assign_follows_the_rules_and_keeps_history(client, make_user):
    admin, agent, other, customer = make_user("admin"), make_user(), make_user(), make_user()
    provider = _approved(client, admin, agent)
    second = _approved(client, admin, other)
    hire = _open_request(client, customer)

    # Candidates: only live providers taking work, with paging
    cands = client.get(f"{H}/{hire['id']}/candidates", params={"q": "Test Agent", "limit": 50}, headers=admin["headers"])
    assert cands.status_code == 200, cands.text
    ids = {c["id"] for c in cands.json()["payload"]["items"]}
    assert {provider["id"], second["id"]} <= ids
    execute("update providers set accepting_work = false where id = %s", (second["id"],))
    ids = {c["id"] for c in client.get(f"{H}/{hire['id']}/candidates", params={"q": "Test Agent", "limit": 50},
                                       headers=admin["headers"]).json()["payload"]["items"]}
    assert second["id"] not in ids
    execute("update providers set accepting_work = true where id = %s", (second["id"],))

    # A note is required, and staff can't push a job forward themselves
    assert _staff(client, admin, hire["id"], "assign", note="", provider_id=provider["id"]).status_code == 422
    assert client.patch(f"{H}/{hire['id']}", json={"status": "completed", "note": "done by staff"},
                        headers=admin["headers"]).status_code == 422
    r = _staff(client, admin, hire["id"], "assign", provider_id=provider["id"])
    assert r.status_code == 200, r.text
    assert r.json()["payload"]["hire"]["status"] == "requested"

    # The assigned provider sees the client's phone only after accepting
    job = client.get(f"{API}/providers/me/jobs", headers=agent["headers"]).json()["payload"]["items"][0]
    assert job["id"] == hire["id"] and job["client_phone"] is None
    assert _bell(client, agent)[0]["title"].startswith("New request")
    assert _bell(client, customer)[0]["title"].startswith("We found a provider")

    # Reassign before acceptance works and tells the first provider
    assert _staff(client, admin, hire["id"], "assign", provider_id=second["id"]).status_code == 200
    assert _bell(client, agent)[0]["title"].startswith("Request moved")
    assert _job(client, other, hire["id"], "accept").status_code == 200
    # Once accepted, no reassignment
    assert _staff(client, admin, hire["id"], "assign", provider_id=provider["id"]).status_code == 409

    detail = client.get(f"{H}/{hire['id']}", headers=admin["headers"]).json()["payload"]
    actions = [e["action"] for e in detail["events"]]
    assert actions[:4] == ["created", "assigned", "reassigned", "accept"]
    staff_events = [e for e in detail["events"] if e["actor_kind"] == "staff"]
    assert all(e["actor"] == admin["email"].lower() or e["actor"] == admin["email"] for e in staff_events)
    assert all(e["note"] for e in staff_events)
    assert "assign" not in detail["actions"] and "cancel" in detail["actions"]
    assert detail["payments"] == [] and detail["tickets"] == []

    # Cancel by staff, then reopen goes back to the queue with no provider
    assert _staff(client, admin, hire["id"], "cancel").status_code == 200
    assert "cancelled by our team" in _bell(client, customer)[0]["title"]
    r = _staff(client, admin, hire["id"], "reopen")
    assert r.status_code == 200 and r.json()["payload"]["hire"]["status"] == "open"
    assert r.json()["payload"]["hire"]["provider_id"] is None
    assert client.get(f"{H}/not-a-uuid", headers=admin["headers"]).status_code == 422


def test_paid_jobs_cannot_be_cancelled_and_complaints_are_decided_once(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    assert _job(client, agent, hire["id"], "accept").status_code == 200
    _deliver(client, agent, hire["id"])
    _pay(client, customer, hire["id"])

    assert _staff(client, admin, hire["id"], "cancel").status_code == 409
    assert _staff(client, admin, hire["id"], "note", note="Called the client, all fine").status_code == 200

    assert client.post(f"{API}/hires/{hire['id']}/dispute", json={"reason": "Passport has a wrong date"},
                       headers=customer["headers"]).status_code == 200
    decide = lambda d: client.post(f"{H}/{hire['id']}/dispute", json={"decision": d, "note": "Confirmed with the office"},  # noqa: E731
                                   headers=admin["headers"])
    assert client.post(f"{H}/{hire['id']}/dispute", json={"decision": "upheld"}, headers=admin["headers"]).status_code == 422
    r = decide("upheld")
    assert r.status_code == 200, r.text
    assert r.json()["payload"]["hire"]["refund_needed"] is True
    assert decide("dismissed").status_code == 409  # no flipping
    assert fetch_one("select dispute_status from engagements where id = %s", (hire["id"],))["dispute_status"] == "upheld"
    assert _bell(client, customer)[0]["title"].startswith("Your complaint about")
    assert _bell(client, agent)[0]["title"].startswith("A complaint about")

    # Staff-only fields never reach the client or the provider
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert "refund_needed" not in mine and "admin_note" not in mine

    refunds = client.get(H, params={"refund_needed": True, "q": hire["id"][:8]}, headers=admin["headers"]).json()["payload"]
    assert [h["id"] for h in refunds["items"]] == [hire["id"]]
    detail = client.get(f"{H}/{hire['id']}", headers=admin["headers"]).json()["payload"]
    assert len(detail["payments"]) == 1 and detail["payments"][0]["status"] == "success"
    assert {"complaint", "complaint_upheld", "refund_needed", "staff_note"} <= {e["action"] for e in detail["events"]}

    # Search by payment reference
    tx = detail["payments"][0]["tx_ref"]
    assert client.get(H, params={"q": tx}, headers=admin["headers"]).json()["payload"]["total"] == 1


def test_status_changes_are_guarded_against_races(client, make_user, monkeypatch):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    stale = svc.get_engagement(hire["id"])
    assert _job(client, agent, hire["id"], "decline", "Fully booked").status_code == 200
    # The client's page still shows "requested": the cancel must not overwrite the decline
    monkeypatch.setattr(svc, "get_engagement", lambda _id: stale)
    try:
        svc.client_action(hire["id"], user_id=customer["id"], action="cancel")
        raise AssertionError("cancel should have been refused")
    except svc.MarketplaceError as exc:
        assert exc.status_code == 409
    monkeypatch.undo()
    assert svc.get_engagement(hire["id"])["status"] == "declined"


def test_hire_export_is_safe_and_needs_its_permission(client, make_user, make_staff):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider, title="=HYPERLINK(\"http://x\") renew")
    r = client.get(f"{H}.csv", params={"q": hire["id"][:8]}, headers=admin["headers"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert "'=HYPERLINK" in r.text and hire["id"] in r.text
    logged = fetch_one("select details from staff_audit_log where action = 'hires.export' and actor_email = lower(%s) "
                       "order by id desc limit 1", (admin["email"],))
    assert logged and logged["details"]["rows"] == 1
    support = make_staff("support_agent")
    assert client.get(f"{H}.csv", headers=support["headers"]).status_code == 403
    assert client.get(H, headers=support["headers"]).status_code == 200
    # Support staff see the hire, but not its payments
    detail = client.get(f"{H}/{hire['id']}", headers=support["headers"]).json()["payload"]
    assert detail["payments"] is None and detail["tickets"] == []


def test_providers_list_sends_no_private_fields(client, make_user):
    admin, agent = make_user("admin"), make_user()
    provider = _approved(client, admin, agent)
    r = client.get(f"{API}/admin/marketplace/providers", params={"q": provider["registration_no"] or "Test Agent",
                                                                 "status": "approved", "sort": "score"},
                   headers=admin["headers"])
    assert r.status_code == 200, r.text
    row = next(p for p in r.json()["payload"]["items"] if p["id"] == provider["id"])
    for private in ("national_id", "tin", "id_document_url", "payout_bank_name", "payout_account_last4",
                    "vat_number", "address", "license_document_url", "email"):
        assert private not in row
    assert {"display_name", "status", "trust_score", "open_jobs", "open_disputes"} <= set(row)
    execute("update providers set license_expires_at = current_date + 10 where id = %s", (provider["id"],))
    soon = client.get(f"{API}/admin/marketplace/providers", params={"expiring": 30, "limit": 100},
                      headers=admin["headers"]).json()["payload"]["items"]
    assert provider["id"] in {p["id"] for p in soon}


def test_sample_removal_is_refused_in_production_and_with_money(client, make_user, monkeypatch):
    from config.config import settings

    admin, agent = make_user("admin"), make_user()
    provider = _approved(client, admin, agent)
    monkeypatch.setattr(settings, "environment", "production")
    r = client.post(f"{API}/admin/marketplace/samples/purge", headers=admin["headers"])
    assert r.status_code == 403
    status = client.get(f"{API}/admin/marketplace/samples", headers=admin["headers"]).json()["payload"]
    assert status["can_purge"] is False
    monkeypatch.undo()

    # A sample provider with an earnings record blocks removal (checked without deleting anything)
    execute("update providers set is_sample = true where id = %s", (provider["id"],))
    execute("insert into provider_ledger (provider_id, kind, amount, note) values (%s, 'adjustment', 1, 'test')",
            (provider["id"],))
    try:
        with connection() as conn:
            assert any("earnings" in b for b in svc._purge_blockers(conn))
        assert svc.sample_status()["can_purge"] is False
    finally:
        execute("delete from provider_ledger where provider_id = %s", (provider["id"],))
        execute("update providers set is_sample = false where id = %s", (provider["id"],))


def test_public_views_hide_job_titles_and_invite_emails(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider, title="Passport for my son Dawit")
    _job(client, agent, hire["id"], "accept")
    _deliver(client, agent, hire["id"])
    _pay(client, customer, hire["id"])
    client.post(f"{API}/hires/{hire['id']}/review", json={"rating": 4, "comment": "Good"}, headers=customer["headers"])
    profile = client.get(f"{API}/providers/{provider['slug']}").json()["payload"]["provider"]
    assert "job_title" not in profile["reviews"]["items"][0]
    assert all("Dawit" not in (j["title"] or "") for j in svc.recent_jobs(provider["id"]))
    assert all("invited_email" not in m for m in svc.team(provider["id"], include_pending=True))
    # Staff still see the title
    reviews = client.get(f"{API}/admin/marketplace/reviews", params={"q": "Test Agent"}, headers=admin["headers"])
    assert any(r["job_title"] == "Passport for my son Dawit" for r in reviews.json()["payload"]["items"])
    rid = profile["reviews"]["items"][0]["id"]
    short = client.post(f"{API}/admin/marketplace/reviews/{rid}/moderate", json={"hidden": True, "reason": "bad"},
                        headers=admin["headers"])
    assert short.status_code == 400
    assert client.post(f"{API}/admin/marketplace/review-changes/nope", json={"decision": "approve"},
                       headers=admin["headers"]).status_code == 422


def test_hire_requests_are_limited(client, make_user, monkeypatch):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    monkeypatch.setattr(svc, "MAX_REQUESTS_PER_HOUR", 2)
    _hire(client, customer, provider)
    _hire(client, customer, provider)
    r = client.post(f"{API}/hires", json={"provider_id": provider["slug"], "title": "Third",
                                          "client_name": "Test Client", "client_phone": "0922000000", "client_telegram": "test_client"},
                    headers=customer["headers"])
    assert r.status_code == 429
    assert fetch_all("select 1 from engagements where client_user_id = %s", (customer["id"],)).__len__() == 2
