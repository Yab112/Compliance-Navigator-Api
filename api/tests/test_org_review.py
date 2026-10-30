"""Staff review of organizations, submissions and "this is wrong" reports (migration 028)."""

import csv
import io
import uuid

from conftest import API
from test_organizations import (  # noqa: F401
    _create_and_publish,
    _register,
    _service,
    _verify,
    graph_cleanup,
)

from services import feedback_service
from services.db import execute, fetch_all, fetch_one


def _notes(user_id, kind):
    return fetch_all("select title, body from notifications where user_id = %s and kind = %s", (user_id, kind))


def test_verify_needs_authorization_letter_and_tells_the_org(client, make_user):
    user, admin = make_user(), make_user("admin")
    org = _register(client, user)
    url = f"{API}/admin/organizations/{org['id']}/review"
    r = client.post(url, json={"action": "verify"}, headers=admin["headers"])
    assert r.status_code == 409 and "authorization letter" in r.json()["detail"]
    assert fetch_one("select status from organizations where id = %s", (org["id"],))["status"] == "pending"

    _verify(client, admin, org["id"])
    assert _notes(user["id"], "org_verify")
    assert client.post(url, json={"action": "suspend", "note": "Letter expired"}, headers=admin["headers"]).status_code == 200
    body = _notes(user["id"], "org_suspend")[0]["body"]
    assert "Letter expired" in body


def test_submission_decisions_notify_members(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org = _register(client, user)
    _verify(client, admin, org["id"])
    r = client.post(f"{API}/org/{org['id']}/services", json=_service("Notice service"), headers=user["headers"])
    sid = r.json()["payload"]["service"]["id"]
    graph_cleanup.append(sid)
    client.post(f"{API}/org/{org['id']}/services/{sid}/submit", headers=user["headers"])
    subs = client.get(f"{API}/admin/submissions", params={"q": org["name"]}, headers=admin["headers"]).json()["payload"]
    assert subs["total"] == 1
    rev = subs["submissions"][0]["id"]
    client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "request_changes", "note": "Add the fee"},
                headers=admin["headers"])
    assert "Add the fee" in _notes(user["id"], "service_changes_requested")[0]["body"]
    client.post(f"{API}/org/{org['id']}/services/{sid}/submit", headers=user["headers"])
    rev = client.get(f"{API}/admin/submissions", params={"org_id": org["id"]},
                     headers=admin["headers"]).json()["payload"]["submissions"][0]["id"]
    assert client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "publish"},
                       headers=admin["headers"]).status_code == 200
    assert _notes(user["id"], "service_published")


def test_links_must_be_http(client, make_user):
    user = make_user()
    org = _register(client, user)
    oid = org["id"]
    for bad in ("javascript:alert(1)", "data:text/html,hi", "ftp://files.example.gov.et/form.pdf"):
        body = _service("Bad link", forms=[{"title": "Application form", "url": bad}])
        assert client.post(f"{API}/org/{oid}/services", json=body, headers=user["headers"]).status_code == 422
        assert client.post(f"{API}/org/{oid}/services", json=_service("Bad", online_url=bad),
                           headers=user["headers"]).status_code == 422
        assert client.patch(f"{API}/org/{oid}", json={"website": bad}, headers=user["headers"]).status_code == 422
        assert client.post(f"{API}/org/{oid}/branches", json={"name": "Branch", "map_url": bad},
                           headers=user["headers"]).status_code == 422
    ok = _service("Good link", forms=[{"title": "Form", "url": "forms.example.gov.et/a.pdf"},
                                      {"title": "Uploaded", "url": "/uploads/public/abc123.pdf"}])
    r = client.post(f"{API}/org/{oid}/services", json=ok, headers=user["headers"])
    assert r.status_code == 201, r.text
    assert [f["url"] for f in r.json()["payload"]["service"]["forms"]] == [
        "https://forms.example.gov.et/a.pdf", "/uploads/public/abc123.pdf"]


def test_invites_need_consent_and_do_not_reveal_accounts(client, make_user):
    owner, existing = make_user(), make_user()
    org = _register(client, owner)
    url = f"{API}/org/{org['id']}/members"
    a = client.post(url, json={"email": existing["email"]}, headers=owner["headers"]).json()["payload"]["organization"]
    b = client.post(url, json={"email": f"nobody-{uuid.uuid4().hex[:8]}@example.com"},
                    headers=owner["headers"]).json()["payload"]["organization"]
    by_email = {m["email"]: m for m in b["members"]}
    invited, unknown = by_email[existing["email"]], next(m for e, m in by_email.items() if e.startswith("nobody-"))
    # Same shape whether or not the email has an account, and no name
    assert invited.keys() == unknown.keys() and not invited["accepted"] and not unknown["accepted"]
    assert invited["fullname"] is None and len(a["members"]) == 2
    assert _notes(existing["id"], "org_invite")

    mine = client.get(f"{API}/organizations/mine", headers=existing["headers"]).json()["payload"]
    assert mine["organizations"] == [] and mine["invites"][0]["org_id"] == org["id"]
    stranger = make_user()
    assert client.post(f"{API}/organizations/invites/{invited['id']}/accept",
                       headers=stranger["headers"]).status_code == 404
    assert client.post(f"{API}/organizations/invites/{invited['id']}/decline",
                       headers=existing["headers"]).status_code == 200
    assert client.get(f"{API}/organizations/mine", headers=existing["headers"]).json()["payload"]["invites"] == []


def test_invite_sends_an_email_that_fits_the_address(client, make_user, monkeypatch):
    from api.v1 import organizations as routes

    sent = []
    monkeypatch.setattr(routes, "send_email", sent.append)
    owner, existing = make_user(), make_user()
    org = _register(client, owner)
    url = f"{API}/org/{org['id']}/members"
    nobody = f"nobody-{uuid.uuid4().hex[:8]}@example.com"
    assert client.post(url, json={"email": existing["email"]}, headers=owner["headers"]).status_code == 200
    assert client.post(url, json={"email": nobody}, headers=owner["headers"]).status_code == 200
    by_to = {e.to: e for e in sent}
    assert org["name"] in by_to[existing["email"]].subject
    assert "/org" in by_to[existing["email"]].text and "create one" not in by_to[existing["email"]].text
    # No account yet: the email says to create one with this exact address
    assert "create one with this email address" in by_to[nobody].text and nobody in by_to[nobody].text


def test_anonymous_reports_are_rate_limited(client, monkeypatch):
    msg = f"Wrong fee [test] {uuid.uuid4().hex[:6]}"
    used = fetch_one("select count(*) as c from feedback_flags where ip = 'testclient' and user_id is null "
                     "and created_at > now() - interval '1 hour'")["c"]
    monkeypatch.setattr(feedback_service.platform_settings, "get_int", lambda key: used + 2)
    body = {"target_type": "other", "message": msg}
    assert client.post(f"{API}/feedback", json=body).status_code == 201
    assert client.post(f"{API}/feedback", json=body).status_code == 201
    r = client.post(f"{API}/feedback", json=body)
    assert r.status_code == 429
    assert fetch_one("select count(*) as c from feedback_flags where message = %s", (msg,))["c"] == 2
    execute("delete from feedback_flags where message = %s", (msg,))


def test_reopening_keeps_history(client, make_user):
    admin, citizen = make_user("admin"), make_user()
    msg = f"Office moved [test] {uuid.uuid4().hex[:6]}"
    fid = client.post(f"{API}/feedback", json={"target_type": "office", "target_id": "x", "message": msg},
                      headers=citizen["headers"]).json()["payload"]["flag"]["id"]
    url = f"{API}/admin/feedback/{fid}"
    assert client.patch(url, json={"status": "resolved", "note": "Address fixed"}, headers=admin["headers"]).status_code == 200
    assert client.patch(url, json={"status": "dismissed"}, headers=admin["headers"]).status_code == 409
    assert _notes(citizen["id"], "report_resolved")
    r = client.patch(url, json={"status": "open", "note": "Still wrong"}, headers=admin["headers"]).json()["payload"]["flag"]
    assert r["status"] == "open" and r["resolved_at"] is None and r["resolution_note"] is None
    assert [(e["action"], e["note"]) for e in r["events"]] == [
        ("created", None), ("resolved", "Address fixed"), ("reopened", "Still wrong")]
    listed = client.get(f"{API}/admin/feedback", params={"q": msg, "target_type": "office"},
                        headers=admin["headers"]).json()["payload"]
    assert listed["total"] == 1
    execute("delete from feedback_flags where id = %s", (fid,))


def test_org_list_completeness_and_csv_export(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org = _register(client, user, name=f"=HYPERLINK(\"x\") Office {uuid.uuid4().hex[:6]}")
    r = client.post(f"{API}/org/{org['id']}/services", json=_service("Export service"), headers=user["headers"])
    graph_cleanup.append(r.json()["payload"]["service"]["id"])
    listed = client.get(f"{API}/admin/organizations", params={"status": "all", "q": org["name"]},
                        headers=admin["headers"]).json()["payload"]
    assert listed["total"] == 1 and listed["items"][0]["completeness"] == r.json()["payload"]["service"]["completeness"]["score"]
    assert listed["confirm_every_days"] >= 7

    user_r = client.get(f"{API}/admin/organizations/export.csv", headers=user["headers"])
    assert user_r.status_code == 403
    exp = client.get(f"{API}/admin/organizations/export.csv", params={"q": org["name"]}, headers=admin["headers"])
    assert exp.status_code == 200 and exp.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(exp.text)))
    assert rows[0][0] == "Name" and len(rows) == 2
    assert rows[1][0] == "'" + org["name"]  # a formula would run in Excel
