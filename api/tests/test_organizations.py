import json
import uuid

import pytest
from conftest import API

from services import org_service
from services.db import execute, fetch_one
from services.graph_service import _query_rows


@pytest.fixture(scope="module")
def graph_cleanup():
    created: list[str] = []
    yield created
    for sid in created:
        org_service.remove_service_from_graph(sid)


def _register(client, user, name=None, org_type="sub_city_office"):
    data = {
        "name": name or f"Test Office {uuid.uuid4().hex[:6]}",
        "org_type": org_type,
        "representative_name": "Almaz Bekele",
        "representative_title": "Head of customer service",
        "official_email": "office@example.gov.et",
        "branches": [{"name": "Main branch", "sub_city": "bole"}],
    }
    r = client.post(f"{API}/organizations", data={"data": json.dumps(data)}, headers=user["headers"])
    assert r.status_code == 201, r.text
    return r.json()["payload"]["organization"]


def _verify(client, admin, org_id):
    # Staff can't verify without an authorization letter; tests skip the upload and point at a placeholder key
    execute("update organizations set authorization_letter_key = coalesce(authorization_letter_key, 'private/test-letter.pdf') "
            "where id = %s", (org_id,))
    r = client.post(f"{API}/admin/organizations/{org_id}/review", json={"action": "verify"}, headers=admin["headers"])
    assert r.status_code == 200, r.text


def _service(name, **extra):
    """A service with the core path fields filled, so staff can publish it."""
    body = {"name": name, "summary": f"{name} for testing", "requirements": [], "questions": [], "steps": [],
            "delivery": "online", "no_documents_required": True, "fee_amount_min": 50,
            "processing_time_text": "Same day"}
    body.update(extra)
    return body


CHANGE = {"change_summary": "Updated for testing"}


def _create_and_publish(client, user, admin, org_id, body, graph_cleanup):
    r = client.post(f"{API}/org/{org_id}/services", json=body, headers=user["headers"])
    assert r.status_code == 201, r.text
    sid = r.json()["payload"]["service"]["id"]
    graph_cleanup.append(sid)
    assert client.post(f"{API}/org/{org_id}/services/{sid}/submit", headers=user["headers"]).status_code == 200
    rev = _pending_revision(client, admin, sid)
    r = client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "publish"}, headers=admin["headers"])
    assert r.status_code == 200, r.text
    return sid


def _pending_revision(client, admin, sid):
    subs = client.get(f"{API}/admin/submissions?status=pending", headers=admin["headers"]).json()["payload"]["submissions"]
    return next(s["id"] for s in subs if s["service_id"] == sid)


def test_register_is_pending_and_hidden(client, make_user):
    user = make_user()
    org = _register(client, user)
    assert org["status"] == "pending"
    assert org["members"][0]["role"] == "owner"
    assert client.get(f"{API}/organizations/{org['slug']}").status_code == 404
    mine = client.get(f"{API}/organizations/mine", headers=user["headers"]).json()["payload"]["organizations"]
    assert any(o["id"] == org["id"] for o in mine)


def test_non_member_cannot_edit(client, make_user):
    owner, stranger = make_user(), make_user()
    org = _register(client, owner)
    assert client.patch(f"{API}/org/{org['id']}", json={"description": "x"}, headers=stranger["headers"]).status_code == 403
    assert client.post(f"{API}/org/{org['id']}/services", json=_service("Hijack"), headers=stranger["headers"]).status_code == 403
    # Invited editors can edit but not manage members
    client.post(f"{API}/org/{org['id']}/members", json={"email": stranger["email"]}, headers=owner["headers"])
    invite = client.get(f"{API}/organizations/mine", headers=stranger["headers"]).json()["payload"]["invites"][0]
    # Invited is not a member yet: nobody joins without saying yes
    assert client.patch(f"{API}/org/{org['id']}", json={"description": "x"}, headers=stranger["headers"]).status_code == 403
    assert client.post(f"{API}/organizations/invites/{invite['id']}/accept", headers=stranger["headers"]).status_code == 200
    assert client.patch(f"{API}/org/{org['id']}", json={"description": "Updated"}, headers=stranger["headers"]).status_code == 200
    assert client.post(f"{API}/org/{org['id']}/members", json={"email": "x@example.com"},
                       headers=stranger["headers"]).status_code == 403


def test_profile_save_keeps_a_verified_org_live_and_editors_cant_change_identity(client, make_user):
    owner, editor = make_user(), make_user()
    org = _register(client, owner)
    _verify(client, make_user("admin"), org["id"])
    client.post(f"{API}/org/{org['id']}/members", json={"email": editor["email"]}, headers=owner["headers"])
    invite = client.get(f"{API}/organizations/mine", headers=editor["headers"]).json()["payload"]["invites"][0]
    client.post(f"{API}/organizations/invites/{invite['id']}/accept", headers=editor["headers"])
    status = lambda: fetch_one("select status from organizations where id = %s", (org["id"],))["status"]  # noqa: E731

    # The profile form sends name and type every time; unchanged values must not send it back to review
    same = {"name": org["name"], "org_type": org["org_type"], "phone": "0911223344"}
    assert client.patch(f"{API}/org/{org['id']}", json=same, headers=editor["headers"]).status_code == 200
    assert status() == "verified"
    # Only an owner can rename it or change who speaks for it
    assert client.patch(f"{API}/org/{org['id']}", json={**same, "name": "Renamed by editor"},
                        headers=editor["headers"]).status_code == 403
    assert client.patch(f"{API}/org/{org['id']}", json={"official_email": "other@example.gov.et"},
                        headers=editor["headers"]).status_code == 403
    assert status() == "verified"
    assert client.patch(f"{API}/org/{org['id']}", json={**same, "name": org["name"] + " Office"},
                        headers=owner["headers"]).status_code == 200
    assert status() == "pending"


def test_publish_requires_verified_org_and_syncs_graph(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org = _register(client, user)
    r = client.post(f"{API}/org/{org['id']}/services", json=_service("Business permit"), headers=user["headers"])
    sid = r.json()["payload"]["service"]["id"]
    graph_cleanup.append(sid)
    client.post(f"{API}/org/{org['id']}/services/{sid}/submit", headers=user["headers"])
    rev = _pending_revision(client, admin, sid)
    blocked = client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "publish"}, headers=admin["headers"])
    assert blocked.status_code == 409

    _verify(client, admin, org["id"])
    assert client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "publish"},
                       headers=admin["headers"]).status_code == 200
    rows = _query_rows("MATCH (s:OrgService {id: $sid})-[:OFFERED_BY]->(o:Organization) RETURN o.id AS org", {"sid": sid})
    assert rows and rows[0]["org"] == org["id"]
    page = client.get(f"{API}/organizations/{org['slug']}").json()["payload"]["organization"]
    assert [s["name"] for s in page["services"]] == ["Business permit"]


def test_revision_keeps_published_version_until_approved(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org = _register(client, user)
    _verify(client, admin, org["id"])
    sid = _create_and_publish(client, user, admin, org["id"], _service("Water connection", fee_amount_min=100),
                              graph_cleanup)
    org_slug = org["slug"]
    edit = _service("Water connection", fee_amount_min=999)
    client.put(f"{API}/org/{org['id']}/services/{sid}", json=edit, headers=user["headers"])
    public = client.get(f"{API}/organizations/{org_slug}/services/water-connection").json()["payload"]["service"]
    assert public["fee_amount_min"] == 100

    no_summary = client.post(f"{API}/org/{org['id']}/services/{sid}/submit", headers=user["headers"])
    assert no_summary.status_code == 400  # a live service must say what changed
    client.post(f"{API}/org/{org['id']}/services/{sid}/submit", json=CHANGE, headers=user["headers"])
    rev = _pending_revision(client, admin, sid)
    detail = client.get(f"{API}/admin/submissions/{rev}", headers=admin["headers"]).json()["payload"]["submission"]
    assert detail["published_snapshot"]["fee_amount_min"] == 100 and detail["snapshot"]["fee_amount_min"] == 999

    no_note = client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "request_changes"}, headers=admin["headers"])
    assert no_note.status_code == 400
    client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "request_changes", "note": "Cite the tariff"},
                headers=admin["headers"])
    public = client.get(f"{API}/organizations/{org_slug}/services/water-connection").json()["payload"]["service"]
    assert public["fee_amount_min"] == 100
    working = client.get(f"{API}/org/{org['id']}/services/{sid}", headers=user["headers"]).json()["payload"]["service"]
    assert working["status"] == "changes_requested" and working["admin_note"] == "Cite the tariff"


def test_eligibility_rules(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org = _register(client, user)
    _verify(client, admin, org["id"])
    body = _service(
        "Trade license",
        requirements=[
            {"key": "id", "name": "Kebele ID"},
            {"key": "lease", "name": "Notarized lease", "required": "conditional"},
            {"key": "permit", "name": "Work permit", "required": "conditional"},
        ],
        questions=[
            {"key": "renting", "prompt": "Are you renting the premises?", "rules": [{"value": "yes", "add_requirements": ["lease"]}]},
            {"key": "foreign", "prompt": "Are you a foreign national?", "rules": [{"value": "yes", "add_requirements": ["permit"]}]},
            {"key": "age", "prompt": "Your age", "type": "number",
             "rules": [{"op": "lt", "value": "18", "ineligible": "Applicants must be 18 or older"}]},
        ],
    )
    bad = dict(body, questions=[{"key": "x", "prompt": "Broken rule", "rules": [{"value": "yes", "add_requirements": ["nope"]}]}])
    assert client.post(f"{API}/org/{org['id']}/services", json=bad, headers=user["headers"]).status_code == 400

    sid = _create_and_publish(client, user, admin, org["id"], body, graph_cleanup)
    r = client.post(f"{API}/organizations/services/{sid}/eligibility",
                    json={"answers": {"renting": "yes", "foreign": False, "age": 30}}).json()["payload"]
    assert r["eligible"] and {c["key"] for c in r["checklist"]} == {"id", "lease"}
    r = client.post(f"{API}/organizations/services/{sid}/eligibility", json={"answers": {"age": 16}}).json()["payload"]
    assert not r["eligible"] and r["ineligible_reasons"] == ["Applicants must be 18 or older"]
    assert set(r["unanswered"]) == {"renting", "foreign"}


def test_cross_org_path_order_and_cycles(client, make_user, graph_cleanup):
    admin = make_user("admin")
    users = [make_user() for _ in range(3)]
    orgs = [_register(client, u, name=f"Path org {i} {uuid.uuid4().hex[:4]}") for i, u in enumerate(users)]
    for o in orgs:
        _verify(client, admin, o["id"])
    id_svc = _create_and_publish(client, users[0], admin, orgs[0]["id"],
                                 _service("Resident ID", outputs=[{"name": "Resident ID card"}], processing_minutes=30),
                                 graph_cleanup)
    tin_svc = _create_and_publish(client, users[1], admin, orgs[1]["id"], _service(
        "TIN registration", processing_minutes=20,
        requirements=[{"key": "id", "name": "Resident ID card", "issuing_service_id": id_svc}]), graph_cleanup)
    lic_svc = _create_and_publish(client, users[2], admin, orgs[2]["id"], _service(
        "Trade license", processing_minutes=15,
        requirements=[{"key": "tin", "name": "TIN certificate", "issuing_service_id": tin_svc},
                      {"key": "id", "name": "Resident ID card", "issuing_service_id": id_svc}]), graph_cleanup)

    path = client.get(f"{API}/organizations/services/{lic_svc}/path").json()["payload"]
    names = [s["name"] for s in path["steps"]]
    assert names == ["Resident ID", "TIN registration", "Trade license"]
    assert path["organizations"] == 3 and path["total_minutes"] == 65 and not path["cycles"]
    assert path["steps"][-1]["is_target"]

    # Make the ID service depend on the license: a cycle must be reported, not loop forever
    cyc = _service("Resident ID", outputs=[{"name": "Resident ID card"}],
                   requirements=[{"key": "lic", "name": "Trade license", "issuing_service_id": lic_svc}])
    client.put(f"{API}/org/{orgs[0]['id']}/services/{id_svc}", json=cyc, headers=users[0]["headers"])
    client.post(f"{API}/org/{orgs[0]['id']}/services/{id_svc}/submit", json=CHANGE, headers=users[0]["headers"])
    client.post(f"{API}/admin/submissions/{_pending_revision(client, admin, id_svc)}/review",
                json={"action": "publish"}, headers=admin["headers"])
    path = client.get(f"{API}/organizations/services/{lic_svc}/path").json()["payload"]
    assert path["cycles"] and len(path["steps"]) == 3

    # Requirements can't point at unpublished services from other organizations
    draft = client.post(f"{API}/org/{orgs[1]['id']}/services", json=_service("Draft only"), headers=users[1]["headers"])
    draft_id = draft.json()["payload"]["service"]["id"]
    graph_cleanup.append(draft_id)
    bad = _service("Needs draft", requirements=[{"key": "d", "name": "Draft doc", "issuing_service_id": draft_id}])
    assert client.post(f"{API}/org/{orgs[2]['id']}/services", json=bad, headers=users[2]["headers"]).status_code == 400


def test_public_never_shows_drafts_or_notes(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org = _register(client, user)
    _verify(client, admin, org["id"])
    r = client.post(f"{API}/org/{org['id']}/services", json=_service("Secret draft"), headers=user["headers"])
    graph_cleanup.append(r.json()["payload"]["service"]["id"])
    assert client.get(f"{API}/organizations/{org['slug']}/services/secret-draft").status_code == 404
    page = client.get(f"{API}/organizations/{org['slug']}").json()["payload"]["organization"]
    text = json.dumps(page)
    assert "Secret draft" not in text
    for private in ("representative_name", "official_email", "authorization_letter_key", "verification_note", "admin_note"):
        assert private not in text
    listing = client.get(f"{API}/organizations", params={"q": org["name"]}).json()["payload"]
    assert all("official_email" not in o for o in listing["items"])


# ---------------------------------------------------------------- depth, drafts and freshness (migration 009)

from datetime import date, timedelta


def _full_org(client, user, admin, *, sub_city="bole"):
    org = _register(client, user)
    _verify(client, admin, org["id"])
    branch = client.get(f"{API}/org/{org['id']}", headers=user["headers"]).json()["payload"]["organization"]["branches"][0]
    return org, branch


def test_registration_draft_resume_and_submit(client, make_user):
    user, admin = make_user(), make_user("admin")
    r = client.post(f"{API}/organizations", data={"data": json.dumps(
        {"name": f"Draft office {uuid.uuid4().hex[:6]}", "org_type": "woreda_office", "draft": True})},
        headers=user["headers"])
    assert r.status_code == 201, r.text
    org = r.json()["payload"]["organization"]
    assert org["status"] == "draft" and org["onboarding_step"] == 1
    # Not sent for verification yet, so staff can't act on it
    assert client.post(f"{API}/admin/organizations/{org['id']}/review", json={"action": "verify"},
                       headers=admin["headers"]).status_code == 409

    oid = org["id"]
    client.patch(f"{API}/org/{oid}", json={"onboarding_step": 3}, headers=user["headers"])
    resumed = client.get(f"{API}/organizations/mine", headers=user["headers"]).json()["payload"]["organizations"]
    assert next(o for o in resumed if o["id"] == oid)["onboarding_step"] == 3

    blocked = client.post(f"{API}/org/{oid}/submit-registration", json={}, headers=user["headers"])
    assert blocked.status_code == 400 and "Representative" in blocked.json()["detail"]
    client.patch(f"{API}/org/{oid}", json={
        "representative_name": "Almaz Bekele", "representative_title": "Head of service",
        "official_email": "office@example.gov.et", "steward_name": "Dawit Haile", "steward_phone": "0911000000",
        "data_commitment": True}, headers=user["headers"])
    client.post(f"{API}/org/{oid}/branches", json={"name": "Woreda office", "hours_schedule": [
        {"day": "mon", "open": "08:30", "close": "17:30", "lunch_start": "12:30", "lunch_end": "13:30"},
        {"day": "tue", "open": "08:30", "close": "17:30", "lunch_start": "12:30", "lunch_end": "13:30"},
        {"day": "sat", "open": "08:30", "close": "12:30"}]}, headers=user["headers"])
    # Staff can't verify without the authorization letter, so it is needed before sending
    check = client.get(f"{API}/org/{oid}/registration-check", headers=user["headers"]).json()["payload"]
    assert any("authorization letter" in p for p in check["problems"])
    blocked = client.post(f"{API}/org/{oid}/submit-registration", json={}, headers=user["headers"])
    assert blocked.status_code == 400 and "authorization letter" in blocked.json()["detail"]
    execute("update organizations set authorization_letter_key = 'private/test-letter.pdf' where id = %s", (oid,))
    check = client.get(f"{API}/org/{oid}/registration-check", headers=user["headers"]).json()["payload"]
    assert check["problems"] == []
    done = client.post(f"{API}/org/{oid}/submit-registration", json={}, headers=user["headers"])
    assert done.status_code == 200 and done.json()["payload"]["organization"]["status"] == "pending"
    assert client.post(f"{API}/org/{oid}/submit-registration", json={}, headers=user["headers"]).status_code == 409
    branch = done.json()["payload"]["organization"]["branches"][0]
    assert branch["hours"] == "Mon to Tue 08:30 to 17:30 (lunch 12:30 to 13:30) · Sat 08:30 to 12:30"


def test_csv_import_reports_rows(client, make_user):
    user, admin = make_user(), make_user("admin")
    org, branch = _full_org(client, user, admin)
    template = client.get(f"{API}/organizations/import-template.csv")
    assert template.status_code == 200 and template.text.startswith("name,")
    header = template.text.splitlines()[0]
    cols = header.split(",")

    def row(**vals):
        return ",".join(f'"{vals.get(c, "")}"' for c in cols)

    csv_text = "\n".join([
        header,
        row(name="Birth certificate", summary="Registers a birth", fee_etb="50", processing_time_text="Same day",
            required_documents="Hospital birth notice (original); Parents' ID cards (copy) (x2)",
            branches=branch["name"], proxy_allowed="with_poa"),
        row(name="Marriage certificate", summary="Registers a marriage", fee_etb="abc", processing_time_text="1 day",
            branches="Nowhere branch"),
        row(summary="A row someone forgot to name", fee_etb="10", processing_time_text="1 day"),
        row(name="Divorce certificate", summary="Registers a divorce", fee_etb="10", processing_time_text="1 day",
            delivery="by post"),
        row(),
    ])
    files = {"file": ("services.csv", csv_text.encode(), "text/csv")}
    dry = client.post(f"{API}/org/{org['id']}/services/import", files=files, data={"dry_run": "true"},
                      headers=user["headers"]).json()["payload"]
    assert dry["ready"] == 1 and dry["errors"] == 3 and dry["created"] == 0
    assert len(dry["rows"]) == 4  # the blank last row is ignored
    bad = next(r for r in dry["rows"] if r["name"] == "Marriage certificate")
    assert "The fee_etb column should be a number, like 302, but it has 'abc'" in bad["errors"]
    assert any("Nowhere branch" in e for e in bad["errors"])
    # A row without a name is reported, not skipped
    unnamed = next(r for r in dry["rows"] if r["name"] == "")
    assert unnamed["status"] == "error" and "name column is empty" in unnamed["errors"][0]
    # Validation errors read as sentences naming the column
    post = next(r for r in dry["rows"] if r["name"] == "Divorce certificate")
    assert post["errors"] == ["The delivery column can only be in_person, online or both. It has 'by post'."]
    other = client.post(f"{API}/org/{org['id']}/services/import", data={"dry_run": "true"}, headers=user["headers"],
                        files={"file": ("services.pdf", b"%PDF", "application/pdf")})
    assert other.status_code == 400 and "CSV" in other.json()["detail"]

    real = client.post(f"{API}/org/{org['id']}/services/import", files=files, data={"dry_run": "false"},
                       headers=user["headers"]).json()["payload"]
    assert real["created"] == 1
    sid = next(r for r in real["rows"] if r["status"] == "created")["service_id"]
    work = client.get(f"{API}/org/{org['id']}/services/{sid}", headers=user["headers"]).json()["payload"]["service"]
    parents = next(r for r in work["requirements"] if r["name"] == "Parents' ID cards")
    assert parents["original_or_copy"] == "copy" and parents["copies"] == 2
    assert work["status"] == "draft" and work["fee_amount_min"] == 50 and work["proxy_allowed"] == "with_poa"
    again = client.post(f"{API}/org/{org['id']}/services/import", files=files, data={"dry_run": "true"},
                        headers=user["headers"]).json()["payload"]
    assert again["ready"] == 0  # the imported name now exists


def test_publish_blocked_without_core_fields(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org, _ = _full_org(client, user, admin)
    thin = {"name": "Thin service", "summary": "Missing most fields", "requirements": [], "questions": [], "steps": []}
    r = client.post(f"{API}/org/{org['id']}/services", json=thin, headers=user["headers"])
    svc = r.json()["payload"]["service"]
    graph_cleanup.append(svc["id"])
    assert len(svc["completeness"]["core_missing"]) == 4 and svc["completeness"]["score"] < 30
    client.post(f"{API}/org/{org['id']}/services/{svc['id']}/submit", headers=user["headers"])
    rev = _pending_revision(client, admin, svc["id"])
    r = client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "publish"}, headers=admin["headers"])
    assert r.status_code == 409 and "Missing" in r.json()["detail"]


def test_scheduled_change_goes_live_on_effective_date(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org, branch = _full_org(client, user, admin)
    body = _service("Building permit", delivery="in_person", branch_ids=[branch["id"]],
                    fee_schedule=[{"category": "ethiopian", "amount_min": 500},
                                  {"category": "foreign_national", "amount_min": 1500}],
                    branch_details=[{"branch_id": branch["id"], "window": "Window 4"}])
    sid = _create_and_publish(client, user, admin, org["id"], body, graph_cleanup)
    url = f"{API}/organizations/{org['slug']}/services/building-permit"
    public = client.get(url).json()["payload"]["service"]
    assert public["fee_amount_min"] == 500 and public["fee_amount_max"] == 1500
    assert public["branches"][0]["window"] == "Window 4" and public["confirmation_due"] is False

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    edit = dict(body, fee_schedule=[{"category": "ethiopian", "amount_min": 650},
                                    {"category": "foreign_national", "amount_min": 1500}])
    client.put(f"{API}/org/{org['id']}/services/{sid}", json=edit, headers=user["headers"])
    past = client.post(f"{API}/org/{org['id']}/services/{sid}/submit",
                       json={"change_summary": "New tariff", "effective_at": "2000-01-01"}, headers=user["headers"])
    assert past.status_code == 400
    client.post(f"{API}/org/{org['id']}/services/{sid}/submit",
                json={"change_summary": "Fee rises to 650 ETB under the new tariff", "change_reason": "Directive 12/2026",
                      "effective_at": tomorrow}, headers=user["headers"])
    rev = _pending_revision(client, admin, sid)
    client.post(f"{API}/admin/submissions/{rev}/review", json={"action": "publish"}, headers=admin["headers"])
    public = client.get(url).json()["payload"]["service"]
    assert public["fee_amount_min"] == 500  # still the old fee until tomorrow
    assert public["upcoming_change"]["effective_at"] == tomorrow
    assert public["upcoming_change"]["fee_amount_min"] == 650

    execute("update org_service_revisions set effective_at = current_date where id = %s", (rev,))
    assert org_service.promote_due_changes(force=True) >= 1
    public = client.get(url).json()["payload"]["service"]
    assert public["fee_amount_min"] == 650 and public["upcoming_change"] is None
    assert public["change_log"][0]["summary"] == "Fee rises to 650 ETB under the new tariff"


def test_freshness_confirmation(client, make_user, graph_cleanup):
    user, admin = make_user(), make_user("admin")
    org, _ = _full_org(client, user, admin)
    sid = _create_and_publish(client, user, admin, org["id"], _service("Water meter"), graph_cleanup)
    execute("update org_services set last_confirmed_at = now() - interval '120 days' where id = %s", (sid,))
    listed = client.get(f"{API}/org/{org['id']}", headers=user["headers"]).json()["payload"]["services"]
    assert next(s for s in listed if s["id"] == sid)["confirmation_due"]
    assert any(s["id"] == sid for s in org_service.services_due_for_confirmation())
    public = client.get(f"{API}/organizations/{org['slug']}/services/water-meter").json()["payload"]["service"]
    assert public["confirmation_due"] and public["confirmed_days_ago"] >= 120

    assert client.post(f"{API}/org/{org['id']}/services/{sid}/confirm", headers=user["headers"]).status_code == 200
    public = client.get(f"{API}/organizations/{org['slug']}/services/water-meter").json()["payload"]["service"]
    assert not public["confirmation_due"] and public["confirmed_days_ago"] == 0
    assert client.post(f"{API}/org/{org['id']}/services/confirm-all", headers=user["headers"]).json()["payload"]["confirmed"] >= 1

    # A suspended organization can't vouch for its services
    r = client.post(f"{API}/admin/organizations/{org['id']}/review", json={"action": "suspend", "note": "Test"},
                    headers=admin["headers"])
    assert r.status_code == 200, r.text
    for url in (f"{API}/org/{org['id']}/services/{sid}/confirm", f"{API}/org/{org['id']}/services/confirm-all"):
        r = client.post(url, headers=user["headers"])
        assert r.status_code == 409 and "suspended" in r.json()["detail"]


def test_branch_of_another_org_cannot_be_deleted(client, make_user):
    a, b = make_user(), make_user()
    org_a, org_b = _register(client, a), _register(client, b)
    theirs = client.get(f"{API}/org/{org_b['id']}", headers=b["headers"]).json()["payload"]["organization"]["branches"][0]
    r = client.delete(f"{API}/org/{org_a['id']}/branches/{theirs['id']}", headers=a["headers"])
    assert r.status_code == 404
    assert fetch_one("select 1 from organization_branches where id = %s", (theirs["id"],))


def test_wrong_info_report_reaches_the_organization(client, make_user, graph_cleanup):
    user, admin, citizen, stranger = make_user(), make_user("admin"), make_user(), make_user()
    org, _ = _full_org(client, user, admin)
    sid = _create_and_publish(client, user, admin, org["id"], _service("Electricity connection"), graph_cleanup)
    r = client.post(f"{API}/feedback", json={"target_type": "org_service", "target_id": sid,
                                             "message": "The fee at the window was 700 ETB, not 50"},
                    headers=citizen["headers"])
    assert r.status_code == 201
    reports = client.get(f"{API}/org/{org['id']}/reports", headers=user["headers"]).json()["payload"]["reports"]
    assert reports[0]["service_name"] == "Electricity connection" and reports[0]["status"] == "open"
    assert client.get(f"{API}/org/{org['id']}/reports", headers=stranger["headers"]).status_code == 403
    done = client.post(f"{API}/org/{org['id']}/reports/{reports[0]['id']}",
                       json={"verdict": "fixed", "response": "Fee schedule corrected"}, headers=user["headers"])
    assert done.status_code == 200, done.text
    # The organization answers, but only staff close the report
    assert done.json()["payload"]["report"]["status"] == "open"
    assert done.json()["payload"]["report"]["org_verdict"] == "fixed"
    old_style = client.post(f"{API}/org/{org['id']}/reports/{reports[0]['id']}",
                            json={"status": "dismissed", "response": "Closing it"}, headers=user["headers"])
    assert old_style.status_code == 422
    flags = client.get(f"{API}/admin/feedback", params={"status": "org_responded", "org_id": org["id"]},
                       headers=admin["headers"]).json()["payload"]["flags"]
    flag = next(f for f in flags if f["id"] == reports[0]["id"])
    assert flag["status"] == "open" and flag["org_response"] == "Fee schedule corrected"
    assert flag["org_name"] == org["name"] and [e["action"] for e in flag["events"]] == ["created", "org_responded"]
    execute("delete from feedback_flags where id = %s", (flag["id"],))


def test_change_notifies_path_owners_and_path_uses_org_data(client, make_user, graph_cleanup):
    user, admin, follower = make_user(), make_user("admin"), make_user()
    org, branch = _full_org(client, user, admin)
    doc = f"test_doc_{uuid.uuid4().hex[:8]}"
    body = _service("Health certificate", delivery="in_person", branch_ids=[branch["id"]],
                    branch_details=[{"branch_id": branch["id"], "window": "Desk 7"}],
                    outputs=[{"name": "Health certificate", "document_id": doc}],
                    requirements=[{"key": "photo", "name": "Passport photo", "original_or_copy": "original",
                                   "copies": 2, "photo_specs": "3x4 cm, white background"}],
                    appointment_required=True, appointment_how="Call the desk a day before")
    sid = _create_and_publish(client, user, admin, org["id"], body, graph_cleanup)

    roadmap_id = str(uuid.uuid4())
    execute(
        "insert into roadmaps (id, user_id, goal, sub_city, snapshot_json) values (%s, %s, 'test', 'bole', %s)",
        (roadmap_id, follower["id"], json.dumps({"id": roadmap_id, "request": {"subCity": "bole"},
                                                  "steps": [{"id": doc, "title": "Health certificate",
                                                             "requiredInputs": [], "rejectionReasons": [],
                                                             "paymentMethods": []}]})),
    )
    try:
        from services.roadmap_service import get_roadmap

        step = get_roadmap(roadmap_id)["steps"][0]
        org_step = step["orgService"]
        assert org_step["serviceId"] == sid and org_step["branch"]["window"] == "Desk 7"
        assert org_step["appointment"]["required"] and org_step["requirements"][0]["photo_specs"].startswith("3x4")
        assert step["issuingAuthority"] == org["name"] and step["feeEtb"] == 50

        client.put(f"{API}/org/{org['id']}/services/{sid}", json=dict(body, fee_amount_min=80), headers=user["headers"])
        client.post(f"{API}/org/{org['id']}/services/{sid}/submit", json={"change_summary": "Fee is now 80 ETB"},
                    headers=user["headers"])
        client.post(f"{API}/admin/submissions/{_pending_revision(client, admin, sid)}/review",
                    json={"action": "publish"}, headers=admin["headers"])
        inbox = client.get(f"{API}/notifications", headers=follower["headers"]).json()["payload"]
        assert inbox["unread"] == 1 and "Fee is now 80 ETB" in inbox["items"][0]["body"]
        assert client.post(f"{API}/notifications/read", json={}, headers=follower["headers"]).json()["payload"]["marked"] == 1
        assert get_roadmap(roadmap_id)["steps"][0]["feeEtb"] == 80
    finally:
        execute("delete from roadmaps where id = %s", (roadmap_id,))
