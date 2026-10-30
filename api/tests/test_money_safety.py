"""Money safety: payouts sent once and to the right account, held money never released early, test money
kept apart, one credit per job, and refunds that always need a second person and add up to the cent."""

import threading
from decimal import Decimal

import pytest

from conftest import API, approve_pending
from services import payment_service
from services.db import execute, fetch_all, fetch_one
from services.payment_service import PaymentError
from test_payments import _earnings, _payout_account
from test_providers import _approved, _deliver, _hire, _job, _pay


def _paid_job(client, make_user, price=1000, *, vat=False, title="Renew my passport"):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    if vat:
        assert client.patch(f"{API}/providers/me", json={"vat_registered": True, "vat_number": "0012345678"},
                            headers=agent["headers"]).status_code == 200
        detail = client.get(f"{API}/admin/marketplace/providers/{provider['id']}",
                            headers=admin["headers"]).json()["payload"]["provider"]
        assert client.post(f"{API}/admin/marketplace/providers/{provider['id']}/changes/{detail['pending_change']['id']}",
                           json={"decision": "approve", "note": "VAT certificate matches the number"},
                           headers=admin["headers"]).status_code == 200
    hire = _hire(client, customer, provider, title=title)
    _job(client, agent, hire["id"], "accept", price=price)
    _deliver(client, agent, hire["id"])
    _pay(client, customer, hire["id"])
    tx = fetch_one("select tx_ref from payments where engagement_id = %s and status = 'success'", (hire["id"],))["tx_ref"]
    return {"admin": admin, "agent": agent, "customer": customer, "provider": provider, "hire": hire, "tx": tx}


def _request_payout(client, agent, amount):
    r = client.post(f"{API}/providers/me/payouts", json={"amount": amount}, headers=agent["headers"])
    assert r.status_code == 201, r.text
    return r.json()["payload"]["payout"]


class FakeGateway:
    """Counts transfers; can be slow, fail, or report a status, without any real money."""

    name = "simulated"

    def __init__(self, *, transfer_status="approved", error: PaymentError | None = None, verify="approved", delay=0.0):
        self.transfers: list[dict] = []
        self.transfer_status, self.error, self.verify, self.delay = transfer_status, error, verify, delay
        self.lock = threading.Lock()

    def transfer(self, **kw):
        import time

        time.sleep(self.delay)
        with self.lock:
            self.transfers.append(kw)
        if self.error:
            raise self.error
        return {"status": self.transfer_status, "reference": kw["reference"]}

    def verify_transfer(self, reference):
        return self.verify


@pytest.fixture
def fake_gateway(monkeypatch):
    def install(**kw):
        gw = FakeGateway(**kw)
        monkeypatch.setattr(payment_service, "gateway", lambda: gw)
        monkeypatch.setattr(payment_service, "gateway_named", lambda name: gw)
        return gw
    return install


# ---------------------------------------------------------------- payouts


def test_two_approvals_at_once_send_the_money_once(client, make_user, fake_gateway):
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 500)
    gw = fake_gateway(transfer_status="paid", delay=0.2)

    start, results = threading.Barrier(2), []

    def approve(who):
        start.wait()
        try:
            results.append(payment_service.decide_payout(payout["id"], decision="approve", note=None, actor=who)["status"])
        except PaymentError as exc:
            results.append(exc.status_code)

    threads = [threading.Thread(target=approve, args=(f"staff-{i}@example.com",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(gw.transfers) == 1  # exactly one bank transfer
    assert sorted(map(str, results)) == ["409", "paid"]
    ledger = fetch_all("select amount from provider_ledger where payout_id = %s", (payout["id"],))
    assert [float(r["amount"]) for r in ledger] == [-500.0]


def test_an_approved_payout_cannot_be_refused_and_released(client, make_user, fake_gateway):
    job = _paid_job(client, make_user)  # 885 ETB earned
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 500)
    fake_gateway(transfer_status="approved")  # Chapa queued it
    decide = lambda body: client.post(f"{API}/admin/marketplace/payouts/{payout['id']}", json=body,  # noqa: E731
                                      headers=job["admin"]["headers"])
    assert decide({"decision": "approve"}).json()["payload"]["payout"]["status"] == "approved"
    refused = decide({"decision": "reject", "note": "changed my mind"})
    assert refused.status_code == 409 and "may already be on its way" in refused.json()["detail"]
    assert _earnings(client, job["agent"])["available"] == 385.0  # still held
    # Once it is paid, the refusal says so instead of guessing it is still on its way
    execute("update payouts set status = 'paid', paid_at = now() where id = %s", (payout["id"],))
    refused = decide({"decision": "reject", "note": "changed my mind"})
    assert refused.status_code == 409 and refused.json()["detail"] == "This payout was already paid, so it can't be refused."
    assert client.post(f"{API}/admin/marketplace/payouts/not-a-uuid", json={"decision": "refresh"},
                       headers=job["admin"]["headers"]).status_code == 422


def test_a_transfer_chapa_refuses_fails_and_releases_the_money(client, make_user, fake_gateway):
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 500)
    fake_gateway(error=PaymentError("Payment service: Bank code must be a numeric", 502, gateway_status=400))
    r = client.post(f"{API}/admin/marketplace/payouts/{payout['id']}", json={"decision": "approve"},
                    headers=job["admin"]["headers"])
    assert r.status_code == 409 and "back in the provider's balance" in r.json()["detail"]
    assert fetch_one("select status from payouts where id = %s", (payout["id"],))["status"] == "failed"
    assert _earnings(client, job["agent"])["available"] == 885.0  # nothing left, nothing held


def test_a_transfer_error_keeps_the_money_held_until_chapa_confirms(client, make_user, fake_gateway):
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 500)
    gw = fake_gateway(error=PaymentError("timed out", 502, uncertain=True))
    decide = lambda body: client.post(f"{API}/admin/marketplace/payouts/{payout['id']}", json=body,  # noqa: E731
                                      headers=job["admin"]["headers"])
    r = decide({"decision": "approve"})
    assert r.status_code == 502 and "stays held" in r.json()["detail"]
    row = fetch_one("select status, needs_check from payouts where id = %s", (payout["id"],))
    assert row == {"status": "approved", "needs_check": True}
    assert _earnings(client, job["agent"])["available"] == 385.0  # not released
    review = client.get(f"{API}/admin/marketplace/payouts/{payout['id']}", headers=job["admin"]["headers"]).json()["payload"]
    assert any(c["code"] == "needs_check" for c in review["checks"])
    # Can't refuse it, and can't mark it failed while Chapa still says it is on its way
    assert decide({"decision": "reject", "note": "transfer failed"}).status_code == 409
    assert decide({"decision": "mark_failed", "note": "Looked in the Chapa dashboard"}).status_code == 409
    gw.verify = "approved"
    assert decide({"decision": "refresh"}).json()["payload"]["payout"]["status"] == "approved"
    gw.verify = "failed"
    assert decide({"decision": "refresh"}).json()["payload"]["payout"]["status"] == "failed"
    assert _earnings(client, job["agent"])["available"] == 885.0  # released only now


def test_mark_failed_when_chapa_never_received_the_transfer(client, make_user, fake_gateway):
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 500)
    # A timeout: Chapa may or may not have it, so the money stays held until someone checks
    gw = fake_gateway(error=PaymentError("timed out", 502, uncertain=True))
    decide = lambda body: client.post(f"{API}/admin/marketplace/payouts/{payout['id']}", json=body,  # noqa: E731
                                      headers=job["admin"]["headers"])
    assert decide({"decision": "approve"}).status_code == 502
    gw.verify = "missing"
    assert decide({"decision": "mark_failed", "note": "short"}).status_code == 400
    assert decide({"decision": "refresh"}).json()["payload"]["payout"]["status"] == "approved"  # refresh alone keeps it
    r = decide({"decision": "mark_failed", "note": "Chapa dashboard shows no such transfer"})
    assert r.json()["payload"]["payout"]["status"] == "failed"
    assert _earnings(client, job["agent"])["available"] == 885.0


def test_the_money_goes_to_the_account_the_payout_was_requested_with(client, make_user, fake_gateway):
    job = _paid_job(client, make_user)
    agent, admin = job["agent"], job["admin"]
    assert _payout_account(client, agent).json()["payload"]["payout"]["name_matches"] is not None
    payout = _request_payout(client, agent, 500)
    # While a payout waits, the account can't change
    r = client.put(f"{API}/providers/me/payout", json={"bank_code": "sim-awash", "account_number": "9999 8888 7777",
                                                       "account_name": "Test Agent"}, headers=agent["headers"])
    assert r.status_code == 409
    me = client.get(f"{API}/providers/me/payout", headers=agent["headers"]).json()["payload"]["payout"]
    assert me["locked"] is True
    # Even if the profile's account changed some other way, the stored one is used
    from core.crypto import encrypt
    execute("update providers set payout_account_enc = %s, payout_account_last4 = '7777' where id = %s",
            (encrypt("999988887777"), job["provider"]["id"]))
    review = client.get(f"{API}/admin/marketplace/payouts/{payout['id']}", headers=admin["headers"]).json()["payload"]
    assert review["destination"]["account_last4"] == "6789" and review["destination"]["stored"] is True
    assert "fayda_name" in review["destination"]
    assert any(c["code"] == "account_changed" for c in review["checks"])
    gw = fake_gateway(transfer_status="paid")
    assert client.post(f"{API}/admin/marketplace/payouts/{payout['id']}", json={"decision": "approve"},
                       headers=admin["headers"]).status_code == 200
    assert gw.transfers[0]["account_number"] == "100023456789" and gw.transfers[0]["bank_code"] == "sim-cbe"
    bell = client.get(f"{API}/notifications", headers=agent["headers"]).json()["payload"]["items"]
    assert any(n["title"] == "Payout bank account added" for n in bell)  # security notice


def test_a_payout_without_a_stored_account_cannot_be_sent(client, make_user, fake_gateway):
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 500)
    execute("update payouts set account_enc = null where id = %s", (payout["id"],))  # an old request
    gw = fake_gateway(transfer_status="paid")
    r = client.post(f"{API}/admin/marketplace/payouts/{payout['id']}",
                    json={"decision": "approve", "note": "I want to approve this anyway"}, headers=job["admin"]["headers"])
    assert r.status_code == 409 and "no bank account stored" in r.json()["detail"] and not gw.transfers


# ---------------------------------------------------------------- test money


def test_test_earnings_are_never_withdrawable_once_live(client, make_user, monkeypatch):
    from config.config import settings

    job = _paid_job(client, make_user)  # paid through the simulated (test) checkout
    agent = job["agent"]
    _payout_account(client, agent)
    waiting = _request_payout(client, agent, 300)  # asked for while in test mode
    assert fetch_one("select is_test from payments where tx_ref = %s", (job["tx"],))["is_test"] is True

    monkeypatch.setattr(settings, "payments_mode", "chapa")
    monkeypatch.setattr(settings, "chapa_secret_key", "CHASECK-live-key-for-tests")
    e = _earnings(client, agent)
    assert e["balance"] == 0 and e["available"] == 0 and e["test_balance"] == 885.0 and e["live"] is True
    assert e["ledger"][0]["is_test"] is True
    assert client.post(f"{API}/providers/me/payouts", json={"amount": 200}, headers=agent["headers"]).status_code == 409
    r = client.post(f"{API}/admin/marketplace/payouts/{waiting['id']}",
                    json={"decision": "approve", "note": "Approving although it says test"}, headers=job["admin"]["headers"])
    assert r.status_code == 409 and "test-mode" in r.json()["detail"]
    # It can still be refused, which releases nothing real
    assert client.post(f"{API}/admin/marketplace/payouts/{waiting['id']}", json={"decision": "reject", "note": "test money"},
                       headers=job["admin"]["headers"]).status_code == 200


# ---------------------------------------------------------------- one credit per job


def test_double_click_on_pay_opens_one_checkout(client, make_user):
    from schemas.auth_user import AuthUser

    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=700)
    _deliver(client, agent, hire["id"])
    user = AuthUser(id=customer["id"], email=customer["email"], fullname="Test User")

    start, results = threading.Barrier(3), []

    def pay():
        start.wait()
        try:
            results.append(payment_service.start(hire["id"], user=user)["tx_ref"])
        except PaymentError as exc:
            results.append(exc.status_code)

    threads = [threading.Thread(target=pay) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = fetch_all("select tx_ref from payments where engagement_id = %s", (hire["id"],))
    assert len(rows) == 1  # one checkout, whatever the timing
    assert all(r in (rows[0]["tx_ref"], 409) for r in results)


def test_a_second_payment_for_the_same_job_is_not_credited(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=1000)
    _deliver(client, agent, hire["id"])
    pay = lambda: client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"]).json()["payload"]  # noqa: E731
    first = pay()["tx_ref"]
    # The first checkout page stays open in another tab; later a second one is opened
    execute("update payments set created_at = now() - interval '2 days' where tx_ref = %s", (first,))
    second = pay()["tx_ref"]
    assert second != first
    sim = lambda tx: client.post(f"{API}/payments/{tx}/simulate", json={"outcome": "success"},  # noqa: E731
                                 headers=customer["headers"]).json()["payload"]["payment"]
    assert sim(second)["unapplied_reason"] is None
    late = sim(first)  # the client also pays the old tab
    assert late["status"] == "success" and late["unapplied_reason"] == "duplicate"
    earnings = fetch_all("select amount from provider_ledger where engagement_id = %s and kind = 'earning'", (hire["id"],))
    assert [float(r["amount"]) for r in earnings] == [885.0]  # credited once
    flagged = fetch_one("select refund_needed, payment_status from engagements where id = %s", (hire["id"],))
    assert flagged == {"refund_needed": True, "payment_status": "paid"}
    listed = client.get(f"{API}/admin/marketplace/payments", params={"needs_refund": "true", "q": first},
                        headers=admin["headers"]).json()["payload"]
    assert [i["tx_ref"] for i in listed["items"]] == [first] and listed["items"][0]["refundable"] == 1000.0
    # Refunding the duplicate takes nothing from the provider and leaves the job paid
    r = client.post(f"{API}/admin/marketplace/payments/{first}/refund", json={"reason": "Paid twice by mistake"},
                    headers=admin["headers"])
    approve_pending(client, r, make_user("admin"))
    assert _earnings(client, agent)["balance"] == 885.0
    assert fetch_one("select payment_status, refund_needed from engagements where id = %s", (hire["id"],)) == \
        {"payment_status": "paid", "refund_needed": False}


def test_a_payment_for_a_cancelled_job_is_not_credited(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=600)
    _deliver(client, agent, hire["id"])
    tx = client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"]).json()["payload"]["tx_ref"]
    execute("update engagements set status = 'cancelled' where id = %s", (hire["id"],))  # staff cancelled meanwhile
    assert client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"]).status_code == 409
    paid = client.post(f"{API}/payments/{tx}/simulate", json={"outcome": "success"},
                       headers=customer["headers"]).json()["payload"]["payment"]
    assert paid["status"] == "success" and paid["unapplied_reason"] == "job_closed"
    assert _earnings(client, agent)["balance"] == 0
    assert fetch_one("select refund_needed from engagements where id = %s", (hire["id"],))["refund_needed"] is True
    assert fetch_one("select action from engagement_events where engagement_id = %s and action = 'refund_needed'",
                     (hire["id"],))


# ---------------------------------------------------------------- refunds


def _refund(client, job, body):
    return client.post(f"{API}/admin/marketplace/payments/{job['tx']}/refund", json=body, headers=job["admin"]["headers"])


def test_full_refund_with_vat_needs_a_second_person_and_reverses_everything(client, make_user):
    job = _paid_job(client, make_user, 1000, vat=True)  # client paid 1150; provider got 1035
    admin, agent, customer = job["admin"], job["agent"], job["customer"]
    assert _refund(client, job, {"reason": "no"}).status_code == 422  # a reason is required
    support = make_user("admin")
    execute("delete from staff_user_roles where staff_id = %s", (support["id"],))
    execute("insert into staff_user_roles (staff_id, role_id, granted_by) select %s, id, 'pytest' from staff_roles "
            "where builtin_key = 'support_agent'", (support["id"],))
    assert client.post(f"{API}/admin/marketplace/payments/{job['tx']}/refund", json={"reason": "Complaint upheld"},
                       headers=support["headers"]).status_code == 403

    r = _refund(client, job, {"reason": "Complaint upheld: the passport was never collected"})
    assert r.status_code == 202  # nothing happens until someone else approves
    assert r.json()["payload"]["approval"]["action"] == "payment.refund"
    assert _earnings(client, agent)["balance"] == 1035.0
    assert _refund(client, job, {"reason": "Asking a second time"}).status_code == 409  # one open request per payment
    own = client.post(f"{API}/admin/access/approvals/{r.json()['payload']['approval']['id']}/approve", json={"note": "ok"},
                      headers=admin["headers"])
    assert own.status_code == 403  # nobody approves their own refund
    decided = approve_pending(client, r, make_user("admin"))
    assert decided["status"] == "executed", decided

    refund = decided["result"]
    assert refund["status"] == "refunded" and refund["amount"] == 1150.0
    pay = fetch_one("select refunded_amount, refunded_commission, refunded_commission_vat, refunded_provider_amount, "
                    "refunded_provider_vat from payments where tx_ref = %s", (job["tx"],))
    assert pay == {"refunded_amount": Decimal("1150.00"), "refunded_commission": Decimal("100.00"),
                   "refunded_commission_vat": Decimal("15.00"), "refunded_provider_amount": Decimal("1035.00"),
                   "refunded_provider_vat": Decimal("150.00")}
    e = _earnings(client, agent)
    assert e["balance"] == 0 and e["refunded"] == 1035.0 and e["ledger"][0]["kind"] == "refund"
    hire = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert hire["payment_status"] == "refunded"
    assert _refund(client, job, {"reason": "Once more please"}).status_code == 409  # nothing left

    receipt = client.get(f"{API}/refunds/{refund['refund_id']}/receipt", headers=customer["headers"]).json()["payload"]["receipt"]
    assert receipt["kind"] == "refund" and receipt["total"] == 1150.0
    assert [line["amount"] for line in receipt["lines"]] == [1000.0, 150.0] and "statement" not in receipt
    statement = client.get(f"{API}/refunds/{refund['refund_id']}/receipt",
                           headers=agent["headers"]).json()["payload"]["receipt"]["statement"]
    assert statement == {"commission": 100.0, "commission_vat": 15.0, "provider_amount": 1035.0, "provider_vat": 150.0}
    assert client.get(f"{API}/refunds/{refund['refund_id']}/receipt",
                      headers=make_user()["headers"]).status_code == 404
    original = client.get(f"{API}/payments/{job['tx']}/receipt", headers=customer["headers"]).json()["payload"]["receipt"]
    assert original["total"] == 1150.0 and original["refunds"][0]["reference"] == refund["reference"]
    for who in (customer, agent):
        bell = client.get(f"{API}/notifications", headers=who["headers"]).json()["payload"]["items"]
        assert any("efund" in n["title"] for n in bell)
    events = fetch_all("select action, actor_kind from engagement_events where engagement_id = %s", (job["hire"]["id"],))
    assert {"action": "refunded", "actor_kind": "staff"} in events
    assert {"action": "refund_done", "actor_kind": "staff"} in events


def test_partial_refunds_without_vat_add_up_to_the_cent(client, make_user):
    job = _paid_job(client, make_user, 1000)  # 1000 paid: 100 commission + 15 VAT on it + 885 provider
    approver = make_user("admin")
    _payout_account(client, job["agent"])
    waiting = _request_payout(client, job["agent"], 600)
    assert _refund(client, job, {"amount": 1000.01, "reason": "Too much"}).status_code == 409
    first = approve_pending(client, _refund(client, job, {"amount": 333.33, "reason": "One step was not done"}), approver)
    rows = fetch_all("select r.amount, r.commission, r.commission_vat, r.provider_amount, r.provider_vat from refunds r "
                     "join payments p on p.id = r.payment_id where p.tx_ref = %s", (job["tx"],))
    assert rows == [{"amount": Decimal("333.33"), "commission": Decimal("33.33"), "commission_vat": Decimal("5.00"),
                     "provider_amount": Decimal("295.00"), "provider_vat": Decimal("0.00")}]
    assert first["result"]["status"] == "refunded"
    hire = fetch_one("select payment_status from engagements where id = %s", (job["hire"]["id"],))
    assert hire["payment_status"] == "paid"  # partly refunded

    # The provider's balance (590) no longer covers the 600 waiting: the payout is blocked
    review = client.get(f"{API}/admin/marketplace/payouts/{waiting['id']}", headers=job["admin"]["headers"]).json()["payload"]
    assert any(c["code"] == "balance_short" for c in review["checks"])
    assert _earnings(client, job["agent"])["available"] == -10.0

    approve_pending(client, _refund(client, job, {"reason": "The rest as well"}), approver)  # empty amount: the rest
    total = fetch_one("select sum(r.amount) as a, sum(r.commission) as c, sum(r.commission_vat) as v, "
                      "sum(r.provider_amount) as p "
                      "from refunds r join payments p on p.id = r.payment_id where p.tx_ref = %s", (job["tx"],))
    assert total == {"a": Decimal("1000.00"), "c": Decimal("100.00"), "v": Decimal("15.00"), "p": Decimal("885.00")}
    assert _earnings(client, job["agent"])["balance"] == 0
    assert fetch_one("select payment_status from engagements where id = %s", (job["hire"]["id"],))["payment_status"] == "refunded"


def test_refund_figures_math():
    payment = {"amount": 1150, "price": 1000, "provider_vat": 150, "commission_amount": 100, "commission_vat": 15,
               "provider_amount": 1035, "refunded_amount": 0, "unapplied_reason": None}
    half = payment_service.refund_figures(payment, 575)
    assert half == {"amount": Decimal("575.00"), "price_part": Decimal("500.00"), "provider_vat": Decimal("75.00"),
                    "commission": Decimal("50.00"), "commission_vat": Decimal("7.50"), "provider_amount": Decimal("517.50")}
    rest = payment_service.refund_figures({**payment, "refunded_amount": 575}, 575)
    assert rest["provider_amount"] + half["provider_amount"] == Decimal("1035.00")
    duplicate = payment_service.refund_figures({**payment, "unapplied_reason": "duplicate"}, 1150)
    assert duplicate["provider_amount"] == 0 and duplicate["price_part"] == Decimal("1150.00")


def test_manual_refund_waits_for_staff_to_send_and_confirm(client, make_user):
    job = _paid_job(client, make_user, 1000)
    body = {"method": "manual", "reason": "Client paid with a card that Chapa can't refund",
            "client_bank": {"bank_name": "Awash Bank", "account_name": "Test Client", "account_number": "5555 4444 3333"}}
    assert _refund(client, job, {**body, "client_bank": None}).status_code == 400
    checker = make_user("admin")
    decided = approve_pending(client, _refund(client, job, body), checker)
    assert "5555" not in str(decided["payload"])  # the account number is stored encrypted, even in the approval
    assert "_enc" not in str(decided["payload"])  # and the encrypted value never leaves the server
    refund = decided["result"]
    assert refund["status"] == "manual_pending"
    assert _earnings(client, job["agent"])["balance"] == 0  # we owe the client from now on
    listed = client.get(f"{API}/admin/marketplace/refunds", params={"tx_ref": job["tx"]},
                        headers=job["admin"]["headers"]).json()["payload"]
    assert listed["total"] == 1 and listed["items"][0]["client_account_number"] == "555544443333"
    assert client.get(f"{API}/refunds/{refund['refund_id']}/receipt", headers=job["customer"]["headers"]).status_code == 404
    act = lambda b, who=checker: client.post(f"{API}/admin/marketplace/refunds/{refund['refund_id']}",  # noqa: E731
                                             json=b, headers=who["headers"])
    # Whoever typed in the client's bank account can't also say the money was sent
    assert act({"action": "confirm", "transfer_reference": "AWB-1", "note": "sent"}, job["admin"]).status_code == 403
    assert act({"action": "confirm"}).status_code == 400  # needs the bank transfer reference
    r = act({"action": "confirm", "transfer_reference": "AWB-778812", "note": "Sent from our Awash account"})
    assert r.status_code == 200 and r.json()["payload"]["refund"]["status"] == "refunded"
    receipt = client.get(f"{API}/refunds/{refund['refund_id']}/receipt",
                         headers=job["customer"]["headers"]).json()["payload"]["receipt"]
    assert receipt["to"]["transfer_reference"] == "AWB-778812" and receipt["to"]["account_last4"] == "3333"


def test_an_unclear_refund_error_needs_checking_and_failing_it_restores_the_share(client, make_user, monkeypatch):
    job = _paid_job(client, make_user, 1000)

    def broken(self, **kw):
        raise PaymentError("timed out", 502, uncertain=True)

    monkeypatch.setattr(payment_service.SimulatedGateway, "refund", broken)
    decided = approve_pending(client, _refund(client, job, {"reason": "Complaint upheld"}), make_user("admin"))
    refund = decided["result"]
    assert refund["status"] == "needs_check"
    assert _earnings(client, job["agent"])["balance"] == 0  # counted until someone checks
    act = lambda b: client.post(f"{API}/admin/marketplace/refunds/{refund['refund_id']}", json=b,  # noqa: E731
                                headers=job["admin"]["headers"])
    assert act({"action": "mark_failed", "note": "short"}).status_code == 400
    r = act({"action": "mark_failed", "note": "Chapa dashboard shows no refund for this payment"})
    assert r.json()["payload"]["refund"]["status"] == "failed"
    assert _earnings(client, job["agent"])["balance"] == 885.0
    state = fetch_one("select payment_status, refund_needed from engagements where id = %s", (job["hire"]["id"],))
    assert state == {"payment_status": "paid", "refund_needed": True}  # the client is still owed
    assert fetch_one("select refunded_amount from payments where tx_ref = %s", (job["tx"],))["refunded_amount"] == 0


def test_a_refused_gateway_refund_changes_nothing(client, make_user, monkeypatch):
    job = _paid_job(client, make_user, 1000)

    def refused(self, **kw):
        raise PaymentError("Payment service: refund not allowed", 502)

    monkeypatch.setattr(payment_service.SimulatedGateway, "refund", refused)
    decided = approve_pending(client, _refund(client, job, {"reason": "Complaint upheld"}), make_user("admin"))
    assert decided["status"] == "failed" and "Nothing was refunded" in decided["error"]
    assert _earnings(client, job["agent"])["balance"] == 885.0
    assert fetch_one("select r.status from refunds r join payments p on p.id = r.payment_id where p.tx_ref = %s",
                     (job["tx"],))["status"] == "failed"


# ---------------------------------------------------------------- staff payments page


def test_payment_totals_add_up_and_staff_tools(client, make_user):
    job = _paid_job(client, make_user, 1000, vat=True, title="Totals check job")
    admin = job["admin"]
    listed = client.get(f"{API}/admin/marketplace/payments", params={"q": job["tx"]}, headers=admin["headers"]).json()["payload"]
    t = listed["totals"]
    assert listed["total"] == 1 and t["paid_count"] == 1
    assert t["gross"] == 1150.0 == t["price"] + t["provider_vat"] == t["commission"] + t["commission_vat"] + t["to_providers"]
    item = listed["items"][0]
    assert item["commission_vat"] == 15.0 and item["provider_vat"] == 150.0 and item["engagement_id"] == job["hire"]["id"]
    assert client.get(f"{API}/admin/marketplace/payments", params={"q": job["tx"], "from": "2000-01-01", "to": "2000-01-02"},
                      headers=admin["headers"]).json()["payload"]["total"] == 0
    csv = client.get(f"{API}/admin/marketplace/payments.csv", params={"q": job["tx"]}, headers=admin["headers"])
    assert csv.status_code == 200 and csv.text.splitlines()[0].startswith("tx_ref,") and job["tx"] in csv.text
    r = client.post(f"{API}/admin/marketplace/payments/{job['tx']}/verify", headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["payment"]["status"] == "success"
    assert client.post(f"{API}/admin/marketplace/payments/cn-nope/verify", headers=admin["headers"]).status_code == 404


def test_staff_can_recheck_a_pending_payment(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=400)
    _deliver(client, agent, hire["id"])
    tx = client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"]).json()["payload"]["tx_ref"]
    verify = lambda: client.post(f"{API}/admin/marketplace/payments/{tx}/verify",  # noqa: E731
                                 headers=admin["headers"]).json()["payload"]
    assert verify()["payment"]["status"] == "pending"
    # The client paid but never came back to our site
    execute("update payments set raw = coalesce(raw, '{}'::jsonb) || '{\"simulated_outcome\": \"success\"}' "
            "where tx_ref = %s", (tx,))
    after = verify()
    assert after["changed"] is True and after["payment"]["status"] == "success"
    assert _earnings(client, agent)["balance"] == 354.0  # 400 - 40 - 6


def test_chapa_transfer_verify_reads_list_and_test_mode_answers(monkeypatch):
    """Chapa answers /transfers/verify with a list; in test mode the record is empty and never settles."""
    from services import payment_service as ps

    gw = ps.ChapaGateway.__new__(ps.ChapaGateway)
    answers = {
        "live-ok": {"message": "Transfer details", "data": [{"reference": "live-ok", "status": "success"}]},
        "live-wait": {"message": "Transfer details", "data": [{"reference": "live-wait", "status": "pending"}]},
        "live-bad": {"message": "Transfer details", "data": {"reference": "live-bad", "status": "failed"}},
        "live-empty": {"message": "Transfer details", "data": [{}]},
        "test-empty": {"message": "Transfer details (Test Mode)", "data": [{}]},
        # Someone else's transfer must never stand in for ours
        "not-mine": {"message": "Transfer details", "data": [{"reference": "other", "status": "failed"}]},
    }
    errors = {
        "gone": ps.PaymentError("Payment service: Transfer not found", 502, gateway_status=404),
        "bad-key": ps.PaymentError("Payment service: Invalid API key", 502, gateway_status=401),
        "slow": ps.PaymentError("Payment service: busy", 502, uncertain=True, gateway_status=503),
    }

    def call(method, path, *a, **k):
        ref = path.rsplit("/", 1)[1]
        if ref in errors:
            raise errors[ref]
        return answers[ref]

    monkeypatch.setattr(gw, "_call", call, raising=False)
    monkeypatch.setattr(ps.settings, "chapa_secret_key", "CHASECK_TEST-x")
    assert gw.verify_transfer("live-ok") == "paid"
    assert gw.verify_transfer("live-wait") == "approved"
    assert gw.verify_transfer("live-bad") == "failed"
    assert gw.verify_transfer("live-empty") == "approved"  # live and unknown: keep the money held
    assert gw.verify_transfer("test-empty") == "paid"
    assert gw.verify_transfer("not-mine") == "approved"
    assert gw.verify_transfer("gone") == "missing"
    assert gw.verify_transfer("bad-key") == "approved"  # a refused key says nothing about the transfer
    assert gw.verify_transfer("slow") == "approved"
    monkeypatch.setattr(ps.settings, "chapa_secret_key", "CHASECK-live")
    assert gw.verify_transfer("test-empty") == "approved"  # the test-mode shortcut needs a test key
