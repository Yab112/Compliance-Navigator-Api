import atexit
import json
from datetime import date, timedelta

import pytest

from conftest import API
from fayda_helpers import ensure_verified
from services import trust_score

PNG = b"\x89PNG\r\n\x1a\nfake"
PASSPORT_RENEWAL = "mesob-728"


def _accept_agreement(client, user):
    from services import legal

    doc = legal.DOCUMENTS["provider_agreement"]
    r = client.post(f"{API}/legal/accept", json={"accept": {doc.key: doc.version}}, headers=user["headers"])
    assert r.status_code == 200, r.text


def _join(client, user, *, verify=True, agree=True, files=None, **overrides):
    if verify:
        ensure_verified(client, user)
    if agree:
        _accept_agreement(client, user)
    data = {
        "provider_type": "guday_geday", "entity_type": "individual",
        "display_name": "Test Agent", "phone": "0911000000",
        "service_areas": ["bole"], "service_ids": [PASSPORT_RENEWAL], "experience_years": 2,
        **overrides,
    }
    return client.post(f"{API}/providers/join", data={"data": json.dumps(data)}, files=files,
                       headers=user["headers"])


_VETTING_FILES: list[str] = []


@atexit.register
def _remove_vetting_files():
    from services.storage_service import delete_vetting_file

    for key in _VETTING_FILES:
        delete_vetting_file(key)


def _vet(provider_id: str) -> None:
    """Hand in and verify every required vetting document, as a provider and staff would."""
    from services import provider_service, vetting
    from services.db import execute, fetch_all

    p = provider_service.get(provider_id)
    if vetting.checklist(p)["complete"]:
        return
    if p["entity_type"] == "individual" and not p.get("telegram_username"):
        execute("update providers set telegram_username = 'test_agent_tg' where id = %s", (provider_id,))
    today = date.today()
    extra = {
        "police_clearance": {"issued_on": today - timedelta(days=10), "reference_no": "FPC-TEST-1"},
        "education": {"level": "grade_12"},
        "trade_licence": {"reference_no": "AA/14/1234", "expires_on": today + timedelta(days=300)},
        "tin_certificate": {"reference_no": "0012345678"},
    }
    for item in vetting.checklist(provider_service.get(provider_id))["items"]:
        if item["type"] != "document" or not item["required"] or item["status"] in ("verified", "expiring"):
            continue
        doc = vetting.upload(p, item["kind"], PNG, actor="test", consent=True, **extra.get(item["kind"], {}))
        vetting.review_document(provider_id, doc["id"], "verified", actor="test", **extra.get(item["kind"], {}))
    _VETTING_FILES.extend(r["file_key"] for r in fetch_all(
        "select file_key from provider_documents where provider_id = %s", (provider_id,)))


def _admin(client, admin, provider_id, action, note=None, vet=True):
    if vet and action == "approve":
        _vet(provider_id)
    if note is None and action in ("approve", "renew"):
        note = "Checked the national ID and references by phone"
    return client.post(f"{API}/admin/marketplace/providers/{provider_id}/review",
                       json={"action": action, "note": note}, headers=admin["headers"])


def _approved(client, admin, user, **overrides) -> dict:
    r = _join(client, user, **overrides)
    assert r.status_code == 201, r.text
    p = r.json()["payload"]["provider"]
    assert _admin(client, admin, p["id"], "approve").status_code == 200
    return p


def _hire(client, customer, provider, **extra):
    r = client.post(f"{API}/hires", json={
        "provider_id": provider["slug"], "title": "Renew my passport",
        "client_name": "Test Client", "client_phone": "0922000000", **extra,
    }, headers=customer["headers"])
    assert r.status_code == 201, r.text
    return r.json()["payload"]["hire"]


PRICE = 800


def _job(client, user, hire_id, action, reason=None, note=None, price=None):
    # Accepting names the price the client pays once the work is delivered
    if action == "accept" and price is None:
        price = PRICE
    return client.post(f"{API}/providers/me/jobs/{hire_id}",
                       json={"action": action, "reason": reason, "note": note, "price": price},
                       headers=user["headers"])


DELIVERED = "Passport renewed and collected from the Bole office."


def _deliver(client, agent, hire_id):
    """Accepted job -> start -> delivered with a note (which requests payment)."""
    assert _job(client, agent, hire_id, "start").status_code == 200
    assert _job(client, agent, hire_id, "complete", note=DELIVERED).status_code == 200


def _pay(client, customer, hire_id):
    """The client pays a delivered job (simulated gateway); paying closes it."""
    r = client.post(f"{API}/hires/{hire_id}/pay", headers=customer["headers"])
    assert r.status_code == 200, r.text
    tx = r.json()["payload"]["tx_ref"]
    r = client.post(f"{API}/payments/{tx}/simulate", json={"outcome": "success"}, headers=customer["headers"])
    assert r.json()["payload"]["payment"]["status"] == "success", r.text


def _deliver_and_close(client, agent, customer, hire_id):
    _deliver(client, agent, hire_id)
    _pay(client, customer, hire_id)


# ---------------------------------------------------------------- joining


def test_join_requires_fayda_and_validates_per_type(client, make_user):
    user = make_user()
    assert _join(client, user, verify=False).status_code == 400  # Fayda first
    assert _join(client, user, phone="12345").status_code == 422
    assert _join(client, user, service_ids=["mesob-nope"]).status_code == 400
    assert _join(client, user, provider_type="delala").status_code == 422  # property brokers are out of scope
    assert _join(client, user, provider_type="agency", service_ids=[]).status_code == 400  # needs specialty
    assert _join(client, user, provider_type="agency", specialties=["spaceships"]).status_code == 400
    assert _join(client, user, provider_type="agency", specialties=["real_estate"]).status_code == 400
    # Companies need legal details and a licence copy
    assert _join(client, user, provider_type="agency", entity_type="company",
                 specialties=["customs_clearing"]).status_code == 400
    company = _join(client, user, provider_type="agency", entity_type="company",
                    display_name="Test Clearing PLC", specialties=["customs_clearing"],
                    legal_name="Test Clearing PLC", tin="0012345678", trade_license_no="AA/14/1234",
                    external_license_type="Customs clearing permit", external_license_no="ECC-77",
                    files={"license_document": ("lic.png", PNG, "image/png")})
    assert company.status_code == 201, company.text
    p = company.json()["payload"]["provider"]
    assert p["slug"].startswith("test-clearing-plc") and p["external_license_status"] == "pending"
    assert _join(client, user).status_code == 409  # one profile per account


def test_individual_agency_join_and_public_listing(client, make_user):
    admin, user = make_user("admin"), make_user()
    r = _join(client, user, provider_type="agency", display_name="Test Clearing Agent",
              specialties=["customs_clearing"], service_ids=[], fee_from=5, fee_unit="percent")
    assert r.status_code == 201, r.text
    p = r.json()["payload"]["provider"]
    assert client.get(f"{API}/providers/{p['slug']}").status_code == 404  # pending is private
    approved = _admin(client, admin, p["id"], "approve").json()["payload"]["provider"]
    assert approved["registration_no"].startswith("AG-")
    listing = client.get(f"{API}/providers", params={"type": "agency", "specialty": "customs_clearing", "area": "bole"}).json()["payload"]
    assert any(i["id"] == p["id"] for i in listing["items"])
    public = client.get(f"{API}/providers/{p['slug']}").json()["payload"]["provider"]
    for secret in ("national_id", "tin", "trade_license_no", "id_document_url", "license_document_url",
                   "review_note", "user_id", "status", "phone", "email"):
        assert secret not in public
        assert all(secret not in i for i in listing["items"])
    assert public["is_new"] is True and public["trust_score"] > 0


# ---------------------------------------------------------------- hires and reviews


def test_hire_lifecycle_and_review_rules(client, make_user):
    admin, agent, customer, stranger = make_user("admin"), make_user(), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    assert hire["status"] == "requested" and "admin_note" not in hire

    review = lambda who, h=hire: client.post(f"{API}/hires/{h['id']}/review", # noqa: E731
                                             json={"rating": 5, "communication": 5, "comment": "Great"},
                                             headers=who["headers"])
    assert review(customer).status_code == 409  # not completed
    assert _job(client, agent, hire["id"], "start").status_code == 409  # must accept first
    assert _job(client, stranger, hire["id"], "accept").status_code == 404
    assert _job(client, agent, hire["id"], "accept", price=None).status_code == 200
    _deliver_and_close(client, agent, customer, hire["id"])

    assert review(stranger).status_code == 403  # only the hiring client
    assert review(customer).status_code == 201
    assert review(customer).status_code == 409  # once per job

    profile = client.get(f"{API}/providers/{provider['slug']}").json()["payload"]["provider"]
    assert profile["rating_count"] == 1 and profile["rating_avg"] == 5.0
    assert profile["reviews"]["items"][0]["comment"] == "Great"
    assert profile["rating_breakdown"]["communication"] == 5.0

    # The provider replies once
    rid = profile["reviews"]["items"][0]["id"]
    reply = lambda: client.post(f"{API}/providers/me/reviews/{rid}/reply", json={"reply": "Thank you"}, # noqa: E731
                                headers=agent["headers"])
    assert reply().status_code == 200 and reply().status_code == 409

    # Hidden reviews disappear from the public page and the score
    mod = client.post(f"{API}/admin/marketplace/reviews/{rid}/moderate", json={"hidden": True},
                      headers=admin["headers"])
    assert mod.status_code == 400  # reason required
    client.post(f"{API}/admin/marketplace/reviews/{rid}/moderate", json={"hidden": True, "reason": "abuse"},
                headers=admin["headers"])
    profile = client.get(f"{API}/providers/{provider['slug']}").json()["payload"]["provider"]
    assert profile["rating_count"] == 0 and profile["reviews"]["total"] == 0


def test_phone_numbers_are_shared_only_after_acceptance(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    assert hire["provider_phone"] is None and hire["contact_shared"] is False
    job = client.get(f"{API}/providers/me/jobs", headers=agent["headers"]).json()["payload"]["items"][0]
    assert job["client_phone"] is None

    assert _job(client, agent, hire["id"], "accept").status_code == 200
    job = client.get(f"{API}/providers/me/jobs", headers=agent["headers"]).json()["payload"]["items"][0]
    assert job["client_phone"] == "0922000000" and job["contact_shared"] is True
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert mine["provider_phone"] == "0911000000"


def test_both_sides_are_notified(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    bell = lambda who: client.get(f"{API}/notifications", headers=who["headers"]).json()["payload"]["items"]  # noqa: E731
    assert bell(agent)[0]["title"] == "New request: Renew my passport" and bell(agent)[0]["link"] == "/me/provider?tab=jobs"
    _job(client, agent, hire["id"], "accept")
    assert bell(customer)[0]["title"] == "Test Agent accepted your request"
    _deliver(client, agent, hire["id"])
    assert bell(customer)[0]["title"] == "Test Agent delivered Renew my passport: please pay"
    assert DELIVERED in bell(customer)[0]["body"] and "800 ETB" in bell(customer)[0]["body"]
    _pay(client, customer, hire["id"])
    assert any(n["title"].endswith("paid 800 ETB for Renew my passport") for n in bell(agent))
    client.post(f"{API}/hires/{hire['id']}/review", json={"rating": 5, "comment": "Great"}, headers=customer["headers"])
    assert bell(agent)[0]["title"].startswith("New 5-star review")


def test_decline_cancel_and_dispute(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    h1 = _hire(client, customer, provider)
    assert _job(client, agent, h1["id"], "decline").status_code == 422  # reason needed
    assert _job(client, agent, h1["id"], "decline", "Fully booked").json()["payload"]["job"]["status"] == "declined"

    h2 = _hire(client, customer, provider)
    assert client.post(f"{API}/hires/{h2['id']}/cancel", headers=customer["headers"]).status_code == 200

    h3 = _hire(client, customer, provider)
    _job(client, agent, h3["id"], "accept")
    assert client.post(f"{API}/hires/{h3['id']}/dispute", json={}, headers=customer["headers"]).status_code == 400
    assert client.post(f"{API}/hires/{h3['id']}/dispute", json={"reason": "Asked for extra cash"},
                       headers=customer["headers"]).status_code == 200
    before = client.get(f"{API}/providers/{provider['slug']}").json()["payload"]["provider"]["trust_score"]
    r = client.post(f"{API}/admin/marketplace/engagements/{h3['id']}/dispute",
                    json={"decision": "upheld", "note": "Confirmed by phone"}, headers=admin["headers"])
    assert r.status_code == 200
    after = client.get(f"{API}/providers/{provider['slug']}").json()["payload"]["provider"]
    assert after["trust_score"] <= before - 9
    assert any(p["key"] == "penalties" for p in after["score_breakdown"])


def test_suspension_hides_provider_and_reopens_jobs(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    assert _admin(client, admin, provider["id"], "suspend").status_code == 400  # reason required
    assert _admin(client, admin, provider["id"], "suspend", "Complaint").status_code == 200
    assert client.get(f"{API}/providers/{provider['slug']}").status_code == 404
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"]
    assert next(h for h in mine if h["id"] == hire["id"])["status"] == "open"
    assert all("admin_note" not in h for h in mine)


def test_other_users_cannot_touch_hires(client, make_user):
    customer, stranger = make_user(), make_user()
    r = client.post(f"{API}/hires", json={"service_id": PASSPORT_RENEWAL, "client_name": "Test Client",
                                          "client_phone": "0922000000"}, headers=customer["headers"])
    hire = r.json()["payload"]["hire"]
    assert hire["status"] == "open"
    assert client.post(f"{API}/hires/{hire['id']}/cancel", headers=stranger["headers"]).status_code == 404


# ---------------------------------------------------------------- agencies


def test_agency_membership_flow(client, make_user):
    admin, owner, member = make_user("admin"), make_user(), make_user()
    agency = _approved(client, admin, owner, provider_type="agency", entity_type="company",
                       display_name="Test Travel Agency", specialties=["travel_visa"], service_ids=[],
                       legal_name="Test Travel PLC", tin="0098765432", trade_license_no="AA/1/99",
                       files={"license_document": ("lic.png", PNG, "image/png")})
    person = _approved(client, admin, member)

    r = client.post(f"{API}/providers/me/agency", json={"agency": agency["slug"]}, headers=member["headers"])
    assert r.status_code == 201
    mid = r.json()["payload"]["membership_id"]
    # The member can't approve their own request; the agency can
    act = lambda who, a: client.post(f"{API}/providers/me/memberships/{mid}", json={"action": a}, # noqa: E731
                                     headers=who["headers"])
    assert act(member, "accept").status_code == 403
    assert act(owner, "accept").json()["payload"]["status"] == "active"

    profile = client.get(f"{API}/providers/{agency['slug']}").json()["payload"]["provider"]
    assert [m["slug"] for m in profile["team"]] == [person["slug"]]
    member_profile = client.get(f"{API}/providers/{person['slug']}").json()["payload"]["provider"]
    assert member_profile["agency"]["slug"] == agency["slug"]
    # A second agency request is refused while active
    again = client.post(f"{API}/providers/me/agency", json={"agency": agency["slug"]}, headers=member["headers"])
    assert again.status_code == 409


def test_profile_edit_and_clearing(client, make_user):
    agent = make_user()
    _join(client, agent, tin="0012345678", address="Bole, near Edna Mall")
    r = client.patch(f"{API}/providers/me", json={"tin": "", "address": None, "headline": "Fast passport help"},
                     headers=agent["headers"])
    assert r.status_code == 200, r.text
    me = r.json()["payload"]["provider"]
    assert me["tin"] is None and me["address"] is None and me["headline"] == "Fast passport help"
    assert "national_id" not in me and me["completeness"]["percent"] < 100


def test_private_files_reject_traversal(client, make_user):
    admin = make_user("admin")
    r = client.get(f"{API}/admin/files", params={"key": "private/../../.env"}, headers=admin["headers"])
    assert r.status_code == 404


# ---------------------------------------------------------------- score math


BASE = dict(review_count=0, review_sum=0, fayda_verified=False, has_phone=False, has_tin=False,
            has_trade_license=False, entity_type="individual", external_license_verified=False,
            completed=0, failed=0, approved_at=None, upheld_disputes=0, suspensions=0)


def test_bayesian_rating_and_new_label():
    assert trust_score.bayesian_rating(0, 0) == pytest.approx(3.5)
    # One 5-star review barely moves the adjusted rating; ten move it a lot
    one = trust_score.bayesian_rating(5, 1)
    ten = trust_score.bayesian_rating(50, 10)
    assert 3.7 < one < 3.8 and ten > 4.4
    assert trust_score.compute({**BASE, "review_count": 2, "review_sum": 10})["is_new"] is True
    assert trust_score.compute({**BASE, "review_count": 3, "review_sum": 15})["is_new"] is False


def test_verification_bonuses_and_penalties():
    bare = trust_score.compute(BASE)["score"]
    verified = trust_score.compute({**BASE, "fayda_verified": True, "has_phone": True, "has_tin": True,
                                    "external_license_verified": True, "police_clearance_verified": True,
                                    "education_verified": True})["score"]
    assert verified - bare == 25
    # Companies only get the registration points with a trade licence too
    company = trust_score.compute({**BASE, "entity_type": "company", "has_tin": True})
    assert next(p for p in company["parts"] if p["key"] == "verification")["points"] == 0
    penalised = trust_score.compute({**BASE, "upheld_disputes": 5, "suspensions": 5})
    assert penalised["score"] == max(0, bare - 30)


def test_photo_upload_replaces_and_removes_file(client, make_user):
    from pathlib import Path

    user = make_user()
    _join(client, user)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    first = client.post(f"{API}/providers/me/photo", files={"photo": ("a.png", png, "image/png")}, headers=user["headers"])
    assert first.status_code == 200, first.text
    first_path = Path("uploads/public") / first.json()["payload"]["photo_url"].rsplit("/", 1)[1]
    assert first_path.is_file()

    pdf = client.post(f"{API}/providers/me/photo", files={"photo": ("a.pdf", b"%PDF-1.4", "application/pdf")}, headers=user["headers"])
    assert pdf.status_code == 400

    second = client.post(f"{API}/providers/me/photo", files={"photo": ("b.png", png, "image/png")}, headers=user["headers"])
    second_path = Path("uploads/public") / second.json()["payload"]["photo_url"].rsplit("/", 1)[1]
    assert second_path.is_file() and not first_path.exists()

    removed = client.delete(f"{API}/providers/me/photo", headers=user["headers"])
    assert removed.status_code == 200
    assert not second_path.exists()
    assert client.get(f"{API}/providers/me", headers=user["headers"]).json()["payload"]["provider"]["photo_url"] is None


def test_tips_do_not_ask_verified_provider_to_verify(client, make_user):
    user = make_user()
    _join(client, user)
    me = client.get(f"{API}/providers/me", headers=user["headers"]).json()["payload"]["provider"]
    assert me["id_verified"]
    assert not any("Fayda" in t for t in me["tips"])


# ---------------------------------------------------------------- the steps of a hire and Job Success


def test_each_step_only_when_it_makes_sense(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    pay = lambda: client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"])  # noqa: E731
    cancel = lambda: client.post(f"{API}/hires/{hire['id']}/cancel", headers=customer["headers"])  # noqa: E731
    review = lambda: client.post(f"{API}/hires/{hire['id']}/review", json={"rating": 5},  # noqa: E731
                                 headers=customer["headers"])

    assert _job(client, agent, hire["id"], "accept", price=0).status_code == 422  # a price is part of accepting
    _job(client, agent, hire["id"], "accept")
    assert pay().status_code == 409  # nothing delivered yet: nothing to pay
    assert _job(client, agent, hire["id"], "complete", note=DELIVERED).status_code == 409  # must start first
    assert _job(client, agent, hire["id"], "start").status_code == 200  # work starts without payment
    assert _job(client, agent, hire["id"], "set_price", price=900).status_code == 200  # still before delivery
    assert _job(client, agent, hire["id"], "complete", note="done").status_code == 400  # say what was delivered
    assert _job(client, agent, hire["id"], "complete", note=DELIVERED).status_code == 200

    # Delivered: the price is fixed, the client can't walk away, only pay or report a problem
    assert _job(client, agent, hire["id"], "set_price", price=1).status_code == 409
    r = cancel()
    assert r.status_code == 409 and "Pay to close" in r.json()["detail"]
    assert client.post(f"{API}/hires/{hire['id']}/complete", headers=customer["headers"]).status_code == 409
    assert review().status_code == 409  # not closed until paid
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert mine["completion_note"] == DELIVERED and mine["agreed_price"] == 900 and mine["payment_requested_at"]

    _pay(client, customer, hire["id"])
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert mine["payment_status"] == "paid" and mine["client_confirmed_at"]  # paying closed it, no other step
    assert pay().status_code == 409
    assert review().status_code == 201


def test_delivered_but_unpaid_reaches_staff_follow_up(client, make_user):
    from services.db import execute

    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept")
    _deliver(client, agent, hire["id"])
    follow = lambda: client.get(f"{API}/admin/marketplace/engagements", params={"follow_up": True},  # noqa: E731
                                headers=admin["headers"]).json()["payload"]["items"]
    assert all(i["id"] != hire["id"] for i in follow())
    execute("update engagements set completed_at = now() - interval '3 days' where id = %s", (hire["id"],))
    assert any(i["id"] == hire["id"] for i in follow())
    # With online payment nothing closes without payment, however long it waits
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert not mine["client_confirmed_at"]


def test_job_success_counts_only_closed_jobs(client, make_user):
    from services import provider_service

    admin, agent = make_user("admin"), make_user()
    provider = _approved(client, admin, agent)
    ratings = [5, 4, None, 2]  # three successes, one failure
    for i, rating in enumerate(ratings):
        customer = make_user()
        hire = _hire(client, customer, provider, title=f"Job {i}")
        _job(client, agent, hire["id"], "accept")
        _deliver_and_close(client, agent, customer, hire["id"])
        if rating:
            client.post(f"{API}/hires/{hire['id']}/review", json={"rating": rating}, headers=customer["headers"])
        if i == 1:  # after two closed jobs: still "New"
            assert provider_service.get(provider["id"])["job_success"] is None
    # An accepted request that isn't paid never closes, so it doesn't count either way
    other = make_user()
    open_hire = _hire(client, other, provider, title="Not paid")
    _job(client, agent, open_hire["id"], "accept")
    p = provider_service.get(provider["id"])
    assert p["closed_jobs"] == 4 and p["job_success"] == 75


def test_renewal_needs_proof_and_only_opens_near_expiry(client, make_user):
    from services.db import execute

    admin, agent = make_user("admin"), make_user()
    p = _approved(client, admin, agent)
    # Just approved: valid for a year, so renewing now proves nothing
    early = _admin(client, admin, p["id"], "renew")
    assert early.status_code == 409 and "Renewal opens on" in early.json()["detail"]

    execute("update providers set license_expires_at = current_date + 10 where id = %s", (p["id"],))
    assert _admin(client, admin, p["id"], "renew", note="ok").status_code == 400  # say what was checked
    r = _admin(client, admin, p["id"], "renew", note="Checked Fayda ID and called two past clients")
    assert r.status_code == 200
    # A second click right after is refused, so the log can't fill with repeat renewals
    assert _admin(client, admin, p["id"], "renew").status_code == 409

    detail = client.get(f"{API}/admin/marketplace/providers/{p['id']}", headers=admin["headers"]).json()["payload"]
    renewals = [e for e in detail["provider"]["events"] if e["action"] == "renew"]
    assert len(renewals) == 1 and "called two past clients" in renewals[0]["note"] and "->" in renewals[0]["note"]
    assert detail["provider"]["renewal"]["blocker"].startswith("The listing is valid until")
    assert detail["provider"]["identity"]["verified_name"]  # what Fayda returned


def test_approval_records_what_was_checked(client, make_user):
    admin, agent = make_user("admin"), make_user()
    r = _join(client, agent)
    pid = r.json()["payload"]["provider"]["id"]
    assert _admin(client, admin, pid, "approve", note="ok").status_code == 400
    assert _admin(client, admin, pid, "approve", note="Fayda ID matches, phone confirmed").status_code == 200
