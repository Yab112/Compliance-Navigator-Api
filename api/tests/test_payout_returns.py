"""Payout returns: a transfer Chapa reported as paid that the bank later sent back. The daily check only flags it;
the money goes back into the provider's balance only once Chapa confirms it and a second staff member approves,
and it is credited exactly once."""

import threading

import pytest

from conftest import API, approve_pending
from services import approvals, payment_service
from services.db import execute, fetch_all, fetch_one
from services.payment_service import PaymentError, gateways
from test_money_safety import _paid_job, _request_payout
from test_payments import _earnings, _payout_account

NOTE = "Bank statement shows the transfer came back on 3 Nov"


class ReturnsGateway(gateways.SimulatedGateway):
    """Like FakeGateway (tests/test_money_safety.py): checkouts and transfers behave as in test mode;
    verify_transfer answers per reference (default "paid") or raises when `down`, and counts the questions."""

    def __init__(self):
        self.answers: dict[str, str] = {}
        self.asked: list[str] = []
        self.down = False
        self.lock = threading.Lock()

    def verify_transfer(self, reference):
        with self.lock:
            self.asked.append(reference)
        if self.down:
            raise PaymentError("The payment service is not reachable right now. Please try again.", 502, uncertain=True)
        return self.answers.get(reference, "paid")


@pytest.fixture
def gw(monkeypatch):
    gateway = ReturnsGateway()
    monkeypatch.setattr(payment_service, "gateway", lambda: gateway)
    monkeypatch.setattr(payment_service, "gateway_named", lambda name: gateway)
    return gateway


def _paid_payout(client, make_user, gw, amount=500, *, chapa=True):
    """885 ETB earned, `amount` paid out to the bank. chapa: recorded as sent through Chapa."""
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], amount)
    r = client.post(f"{API}/admin/marketplace/payouts/{payout['id']}", json={"decision": "approve"},
                    headers=job["admin"]["headers"])
    assert r.status_code == 200 and r.json()["payload"]["payout"]["status"] == "paid", r.text
    if chapa:
        execute("update payouts set gateway = 'chapa' where id = %s", (payout["id"],))
    job["payout"] = fetch_one("select id::text, reference, amount::float, is_test from payouts where id = %s",
                              (payout["id"],))
    return job


def _decide(client, job, body, who=None):
    return client.post(f"{API}/admin/marketplace/payouts/{job['payout']['id']}", json=body,
                       headers=(who or job["admin"])["headers"])


def _payout(job):
    return fetch_one("select status, needs_check, check_note, returned_at, returned_by, return_note from payouts "
                     "where id = %s", (job["payout"]["id"],))


def _ledger(job):
    return [(r["kind"], float(r["amount"]), r["is_test"]) for r in fetch_all(
        "select kind, amount, is_test from provider_ledger where payout_id = %s order by id", (job["payout"]["id"],))]


# ---------------------------------------------------------------- the gateway's answer


@pytest.mark.parametrize("chapa_status, ours", [
    ("success", "paid"), ("failed", "failed"), ("reversed", "failed"), ("returned", "failed"),
    ("bounced", "failed"), ("refunded", "failed"), ("Cancelled", "failed"), ("pending", "approved"),
    ("", "approved"),
])
def test_chapa_transfer_statuses(monkeypatch, chapa_status, ours):
    from config.config import settings

    monkeypatch.setattr(settings, "chapa_secret_key", "CHASECK-unit-not-a-test-key")
    monkeypatch.setattr(gateways.ChapaGateway, "_call",
                        lambda self, method, path, json=None, data=None: {"data": {"reference": "po-1", "status": chapa_status}})
    assert gateways.ChapaGateway().verify_transfer("po-1") == ours


def test_only_not_found_means_missing(monkeypatch):
    from config.config import settings

    monkeypatch.setattr(settings, "chapa_secret_key", "CHASECK-unit-not-a-test-key")

    def answer(status, message, uncertain=False):
        def call(self, *a, **k):
            raise PaymentError(f"Payment service: {message}", 502, uncertain=uncertain, gateway_status=status)
        return call

    monkeypatch.setattr(gateways.ChapaGateway, "_call", answer(404, "Transfer not found"))
    assert gateways.ChapaGateway().verify_transfer("po-1") == "missing"
    monkeypatch.setattr(gateways.ChapaGateway, "_call", answer(401, "Invalid API key"))
    assert gateways.ChapaGateway().verify_transfer("po-1") == "approved"
    monkeypatch.setattr(gateways.ChapaGateway, "_call", answer(503, "Unavailable", uncertain=True))
    assert gateways.ChapaGateway().verify_transfer("po-1") == "approved"


# ---------------------------------------------------------------- the daily check


def test_the_daily_check_flags_a_bounced_transfer_and_leaves_the_ledger_alone(client, make_user, gw):
    job = _paid_payout(client, make_user, gw)
    ref = job["payout"]["reference"]
    before = _earnings(client, job["agent"])
    gw.answers[ref] = "failed"
    counts = payment_service.check_paid_payouts()
    assert ref in gw.asked and counts["flagged"] >= 1
    row = _payout(job)
    assert row["status"] == "paid" and row["needs_check"] is True
    assert row["check_note"] == ("Chapa now reports this transfer failed or was returned after we recorded it as "
                                 "paid. Check the bank and Chapa, then use Transfer came back.")
    assert _ledger(job) == [("payout", -500.0, job["payout"]["is_test"])]
    after = _earnings(client, job["agent"])
    assert {k: after[k] for k in ("balance", "available", "paid_out")} == \
        {k: before[k] for k in ("balance", "available", "paid_out")} == {"balance": 385.0, "available": 385.0,
                                                                         "paid_out": 500.0}
    # The provider does not see the staff note
    mine = client.get(f"{API}/providers/me/payouts", headers=job["agent"]["headers"]).json()["payload"]["items"]
    assert "check_note" not in mine[0] and "needs_check" not in mine[0]
    # Already flagged: not asked again
    gw.asked.clear()
    payment_service.check_paid_payouts()
    assert ref not in gw.asked
    # Payment health and the Payouts page show it
    item = {i["reference"]: i for i in payment_service.attention()["items"]}[ref]
    assert item["problem"] == "returned" and item["status"] == "paid" and item["reason"] == row["check_note"]
    listed = client.get(f"{API}/admin/marketplace/payouts?status=paid", headers=job["admin"]["headers"]).json()["payload"]
    assert listed["items"][0]["id"] == job["payout"]["id"] and listed["items"][0]["needs_check"] is True
    assert listed["totals"]["paid_needs_check"] >= 1


def test_the_daily_check_ignores_paid_missing_errors_old_and_non_chapa_payouts(client, make_user, gw):
    still_paid = _paid_payout(client, make_user, gw)
    missing = _paid_payout(client, make_user, gw)
    old = _paid_payout(client, make_user, gw)
    simulated = _paid_payout(client, make_user, gw, chapa=False)
    gw.answers[missing["payout"]["reference"]] = "missing"
    gw.answers[old["payout"]["reference"]] = "failed"
    gw.answers[simulated["payout"]["reference"]] = "failed"
    execute("update payouts set paid_at = now() - interval '31 days' where id = %s", (old["payout"]["id"],))
    payment_service.check_paid_payouts(days=30)
    assert old["payout"]["reference"] not in gw.asked and simulated["payout"]["reference"] not in gw.asked
    for job in (still_paid, missing, old, simulated):
        assert _payout(job)["needs_check"] is False and _payout(job)["status"] == "paid"
    # Chapa unreachable: nothing changes, and the run goes on
    gw.down = True
    gw.answers[still_paid["payout"]["reference"]] = "failed"
    counts = payment_service.check_paid_payouts()
    assert counts["errors"] >= 1 and _payout(still_paid)["needs_check"] is False
    # Check with Chapa on a flagged payout clears the flag only when Chapa says it is paid again
    gw.down = False
    payment_service.check_paid_payouts()
    assert _payout(still_paid)["needs_check"] is True
    gw.answers[still_paid["payout"]["reference"]] = "paid"
    assert _decide(client, still_paid, {"decision": "refresh"}).json()["payload"]["payout"]["needs_check"] is False
    assert _payout(still_paid)["status"] == "paid"


def test_the_daily_check_is_scheduled():
    from worker import tasks
    from worker.celery_app import celery_app

    beat = {v["task"]: v for v in celery_app.conf.beat_schedule.values()}
    assert beat["worker.tasks.check_paid_payouts"]["schedule"] == 60 * 60 * 24
    assert callable(tasks.check_paid_payouts)


# ---------------------------------------------------------------- staff: Transfer came back


def test_returned_is_refused_while_chapa_says_paid_missing_or_cannot_be_reached(client, make_user, gw):
    job = _paid_payout(client, make_user, gw)
    ref = job["payout"]["reference"]
    short = _decide(client, job, {"decision": "returned", "note": "bounced"})
    assert short.status_code == 400
    r = _decide(client, job, {"decision": "returned", "note": NOTE})
    assert r.status_code == 409 and "still reports this transfer as paid" in r.json()["detail"]
    gw.answers[ref] = "missing"
    r = _decide(client, job, {"decision": "returned", "note": NOTE})
    assert r.status_code == 409 and "no record" in r.json()["detail"]
    gw.answers[ref] = "approved"
    assert _decide(client, job, {"decision": "returned", "note": NOTE}).status_code == 409
    gw.down = True
    r = _decide(client, job, {"decision": "returned", "note": NOTE})
    assert r.status_code == 409 and "Nothing was changed" in r.json()["detail"]
    assert _payout(job)["status"] == "paid" and len(_ledger(job)) == 1
    assert not fetch_one("select 1 as x from approval_requests where target = %s", (f"payout:{job['payout']['id']}",))


def test_returned_waits_for_a_second_person_and_credits_once(client, make_user, gw):
    job = _paid_payout(client, make_user, gw)
    checker = make_user("admin")
    gw.answers[job["payout"]["reference"]] = "failed"
    asked = _decide(client, job, {"decision": "returned", "note": NOTE})
    assert asked.status_code == 202, asked.text
    req = asked.json()["payload"]["approval"]
    assert req["action"] == "payout.returned" and req["status"] == "pending" and "500.00 ETB" in req["summary"]
    # Nothing moved yet
    assert _payout(job)["status"] == "paid" and len(_ledger(job)) == 1
    assert _earnings(client, job["agent"])["balance"] == 385.0
    # Asking twice while one waits is refused
    assert _decide(client, job, {"decision": "returned", "note": NOTE}).status_code == 409
    # The requester can't approve it
    own = client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={"note": "ok"},
                      headers=job["admin"]["headers"])
    assert own.status_code == 403
    decided = approve_pending(client, asked, checker)
    assert decided["status"] == "executed", decided
    row = _payout(job)
    assert row["status"] == "returned" and row["returned_at"] is not None and row["return_note"] == NOTE
    assert job["admin"]["email"] in row["returned_by"] and checker["email"] in row["returned_by"]
    is_test = job["payout"]["is_test"]
    assert _ledger(job) == [("payout", -500.0, is_test), ("payout_return", 500.0, is_test)]
    line = fetch_one("select note from provider_ledger where payout_id = %s and kind = 'payout_return'",
                     (job["payout"]["id"],))
    assert line["note"] == "Transfer to Commercial Bank of Ethiopia ••••6789 came back"
    e = _earnings(client, job["agent"])
    assert (e["balance"], e["available"], e["paid_out"], e["earned_total"], e["in_payout"]) == (885.0, 885.0, 0.0,
                                                                                               885.0, 0.0)
    assert any(entry["kind"] == "payout_return" and entry["amount"] == 500.0 for entry in e["ledger"])
    mine = {p["id"]: p for p in e["payouts"]}[job["payout"]["id"]]
    assert mine["status"] == "returned" and "return_note" not in mine and "returned_by" not in mine
    bell = client.get(f"{API}/notifications", headers=job["agent"]["headers"]).json()["payload"]["items"]
    assert any("came back" in n["title"] and "back in your balance" in (n["body"] or "") for n in bell)
    # The provider can ask for the money again
    assert _request_payout(client, job["agent"], 885)["status"] == "requested"
    # No receipt for a transfer that came back
    assert client.get(f"{API}/payouts/{job['payout']['id']}/receipt", headers=job["agent"]["headers"]).status_code == 404


def test_a_returned_payout_cannot_be_returned_again_failed_or_refused(client, make_user, gw):
    job = _paid_payout(client, make_user, gw)
    gw.answers[job["payout"]["reference"]] = "failed"
    approve_pending(client, _decide(client, job, {"decision": "returned", "note": NOTE}), make_user("admin"))
    again = _decide(client, job, {"decision": "returned", "note": NOTE})
    assert again.status_code == 409 and "already recorded as returned" in again.json()["detail"]
    assert _decide(client, job, {"decision": "mark_failed", "note": NOTE}).status_code == 409
    assert _decide(client, job, {"decision": "reject", "note": NOTE}).status_code == 409
    assert _decide(client, job, {"decision": "approve"}).status_code == 409
    assert _decide(client, job, {"decision": "refresh"}).json()["payload"]["payout"]["status"] == "returned"
    # Running the stored action again (a second approval request) credits nothing
    with pytest.raises(PaymentError) as exc:
        payment_service.execute_payout_return({"payout_id": job["payout"]["id"], "note": NOTE}, "replay")
    assert exc.value.status_code == 409
    assert [k for k, _, _ in _ledger(job)] == ["payout", "payout_return"]
    assert _earnings(client, job["agent"])["balance"] == 885.0


def test_returned_needs_chapa_to_still_say_so_when_it_is_approved(client, make_user, gw):
    job = _paid_payout(client, make_user, gw)
    gw.answers[job["payout"]["reference"]] = "failed"
    asked = _decide(client, job, {"decision": "returned", "note": NOTE})
    gw.answers[job["payout"]["reference"]] = "paid"  # Chapa changed its answer before the approval
    decided = approve_pending(client, asked, make_user("admin"))
    assert decided["status"] == "failed" and "still reports this transfer as paid" in decided["error"]
    assert _payout(job)["status"] == "paid" and len(_ledger(job)) == 1


def test_two_returns_at_once_credit_once(client, make_user, gw):
    job = _paid_payout(client, make_user, gw)
    gw.answers[job["payout"]["reference"]] = "failed"
    start, results = threading.Barrier(4), []

    def run(i):
        start.wait()
        try:
            results.append(payment_service.execute_payout_return({"payout_id": job["payout"]["id"], "note": NOTE},
                                                                 f"staff-{i}@example.com")["status"])
        except PaymentError as exc:
            results.append(exc.status_code)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(map(str, results)) == ["409", "409", "409", "returned"]
    assert [k for k, _, _ in _ledger(job)] == ["payout", "payout_return"]
    assert _earnings(client, job["agent"])["balance"] == 885.0


def test_two_approvers_at_once_credit_once(client, make_user, make_staff, gw):
    job = _paid_payout(client, make_user, gw)
    gw.answers[job["payout"]["reference"]] = "failed"
    req = _decide(client, job, {"decision": "returned", "note": NOTE}).json()["payload"]["approval"]
    checkers = [make_user("admin"), make_user("admin")]
    start, codes = threading.Barrier(2), []

    def approve(who):
        start.wait()
        codes.append(client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={"note": "ok"},
                                 headers=who["headers"]).status_code)

    threads = [threading.Thread(target=approve, args=(c,)) for c in checkers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200, 409]
    assert [k for k, _, _ in _ledger(job)] == ["payout", "payout_return"]
    assert _payout(job)["status"] == "returned"


def test_returned_needs_payout_rights(client, make_user, make_staff, gw):
    job = _paid_payout(client, make_user, gw)
    gw.answers[job["payout"]["reference"]] = "failed"
    ops = make_staff("operations_manager")  # sees payouts and decides approvals, but can't move payout money
    r = _decide(client, job, {"decision": "returned", "note": NOTE}, who=ops)
    assert r.status_code == 403
    req = _decide(client, job, {"decision": "returned", "note": NOTE}).json()["payload"]["approval"]
    r = client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={"note": "ok"}, headers=ops["headers"])
    assert r.status_code == 403
    assert _payout(job)["status"] == "paid"
    # Finance may approve it
    r = client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={"note": "ok"},
                    headers=make_staff("finance")["headers"])
    assert r.status_code == 200 and r.json()["payload"]["approval"]["status"] == "executed"


def test_returned_runs_at_once_only_when_nobody_else_could_approve(client, make_user, gw, monkeypatch):
    job = _paid_payout(client, make_user, gw)
    gw.answers[job["payout"]["reference"]] = "failed"
    monkeypatch.setattr(approvals, "eligible_approvers", lambda *a, **k: [])
    from config.config import settings

    monkeypatch.setattr(settings, "environment", "production")
    waiting = _decide(client, job, {"decision": "returned", "note": NOTE})
    assert waiting.status_code == 202 and _payout(job)["status"] == "paid"  # production: waits for a second person
    execute("update approval_requests set status = 'cancelled' where id = %s",
            (waiting.json()["payload"]["approval"]["id"],))
    monkeypatch.setattr(settings, "environment", "development")
    r = _decide(client, job, {"decision": "returned", "note": NOTE})
    assert r.status_code == 200 and r.json()["payload"]["payout"]["status"] == "returned"
    assert [k for k, _, _ in _ledger(job)] == ["payout", "payout_return"]
