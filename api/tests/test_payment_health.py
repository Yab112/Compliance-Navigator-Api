"""Payment health: every Chapa call is recorded (and recording never gets in the way of a payment), the
status rules, recent errors linked to what they belong to, money that needs a person, and who may see it."""

import uuid
from decimal import Decimal

import httpx
import pytest

from conftest import API
from config.config import settings
from services import payment_service
from services.db import execute, fetch_all, fetch_one
from services.payment_service import ChapaGateway, PaymentError, calls, gateways, health
from test_money_safety import _paid_job, _request_payout
from test_payments import _payout_account

TEST_KEY = "CHASECK_TEST-health-unit-secret"


@pytest.fixture(autouse=True)
def _migrated(client):
    """Starting the app applies the migrations (gateway_calls among them)."""


class Answer:
    def __init__(self, status_code=200, body=None, content_type="application/json"):
        self.status_code, self.body = status_code, body if body is not None else {}
        self.headers = {"content-type": content_type}

    def json(self):
        return self.body


@pytest.fixture
def chapa(monkeypatch):
    """A Chapa gateway whose HTTP answers come from `answer(method, url, **kw)`; nothing leaves the machine."""
    monkeypatch.setattr(settings, "chapa_secret_key", TEST_KEY)
    sent = []

    def install(answer):
        def fake(method, url, **kw):
            sent.append((method, url))
            return answer(method, url, **kw)
        monkeypatch.setattr(gateways.httpx, "request", fake)
        return ChapaGateway()
    install.sent = sent
    return install


def _ref(prefix="cn-health"):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _rows(reference):
    return fetch_all("select * from gateway_calls where reference = %s order by id", (reference,))


@pytest.fixture
def cleanup():
    refs: list[str] = []
    yield refs
    for ref in refs:
        execute("delete from gateway_calls where reference = %s", (ref,))


# ---------------------------------------------------------------- recording


def test_a_successful_call_is_recorded_without_secrets(chapa, cleanup):
    tx = _ref()
    cleanup.append(tx)
    gw = chapa(lambda m, u, **kw: Answer(200, {"status": "success", "data": {"status": "success", "amount": "10",
                                                                             "currency": "ETB"}}))
    assert gw.verify(tx)["status"] == "success"
    [row] = _rows(tx)
    assert row["gateway"] == "chapa" and row["operation"] == "verify" and row["method"] == "GET"
    assert row["path"] == "/transaction/verify/{ref}" and row["reference"] == tx
    assert row["http_status"] == 200 and row["ok"] and not row["uncertain"] and row["error"] is None
    assert row["is_test"] and row["duration_ms"] >= 0
    assert TEST_KEY not in str(row)


def test_a_chapa_error_answer_is_recorded_with_its_message_and_no_account_number(chapa, cleanup):
    reference = _ref("po")
    cleanup.append(reference)
    gw = chapa(lambda m, u, **kw: Answer(400, {"status": "failed", "message": {
        "account_number": ["The account number 1000123456789 is not valid for client@gmail.com"]}}))
    with pytest.raises(PaymentError) as exc:
        gw.transfer(account_name="Test Agent", account_number="1000123456789", bank_code="946", amount=Decimal("500.00"),
                    reference=reference)
    assert not exc.value.uncertain and exc.value.gateway_status == 400
    [row] = _rows(reference)
    assert row["operation"] == "transfer" and row["path"] == "/transfers"
    assert row["http_status"] == 400 and not row["ok"] and not row["uncertain"]
    assert "not valid" in row["error"] and "••••6789" in row["error"] and "[email]" in row["error"]
    assert "1000123456789" not in str(row) and "client@gmail.com" not in str(row) and TEST_KEY not in str(row)


def test_a_server_error_is_recorded_as_uncertain(chapa, cleanup):
    ref_id = _ref("rf")
    cleanup.append(ref_id)
    gw = chapa(lambda m, u, **kw: Answer(503, {}, content_type="text/html"))
    assert gw.verify_refund(ref_id) == "processing"
    [row] = _rows(ref_id)
    assert row["operation"] == "verify_refund" and row["path"] == "/refund/{ref}/verify"
    assert row["http_status"] == 503 and not row["ok"] and row["uncertain"] and "503" in row["error"]


def test_a_timeout_is_recorded_as_uncertain_with_no_status(chapa, cleanup):
    tx = _ref()
    cleanup.append(tx)

    def slow(m, u, **kw):
        raise httpx.ReadTimeout("timed out")
    gw = chapa(slow)
    with pytest.raises(PaymentError) as exc:
        gw.initialize(tx_ref=tx, amount=Decimal("10.00"), email=None, first_name="A", last_name="B", phone=None,
                      return_url="r", callback_url="c", title="t", reason="r")
    assert exc.value.uncertain and exc.value.status_code == 502
    [row] = _rows(tx)
    assert row["operation"] == "initialize" and row["http_status"] is None
    assert not row["ok"] and row["uncertain"] and "ReadTimeout" in row["error"]


def test_a_connection_error_is_recorded(chapa, cleanup):
    tx = _ref()
    cleanup.append(tx)

    def refused(m, u, **kw):
        raise httpx.ConnectError("Connection refused")
    gw = chapa(refused)
    assert gw.verify(tx)["status"] == "pending"
    [row] = _rows(tx)
    assert row["uncertain"] and row["http_status"] is None and "ConnectError" in row["error"]


def test_a_recording_failure_never_breaks_the_call(chapa, monkeypatch, cleanup):
    tx = _ref()
    cleanup.append(tx)
    gw = chapa(lambda m, u, **kw: Answer(200, {"status": "success", "data": [{"id": 1, "name": "CBE"}]}))

    def broken(**kw):
        raise RuntimeError("database is gone")
    monkeypatch.setattr(calls, "record", broken)
    assert gw.banks() == [{"code": "1", "name": "CBE"}]

    # A failed call still raises the payment error, never the recording error
    gw = chapa(lambda m, u, **kw: Answer(400, {"status": "failed", "message": "Invalid tx_ref"}))
    with pytest.raises(PaymentError):
        gw.transfer(account_name="A", account_number="1000123456789", bank_code="1", amount=Decimal("1.00"),
                    reference=tx)


def test_a_database_problem_inside_recording_is_swallowed(chapa, monkeypatch, cleanup):
    tx = _ref()
    cleanup.append(tx)
    gw = chapa(lambda m, u, **kw: Answer(200, {"status": "success", "data": {"status": "success"}}))

    def no_pool(timeout=None):
        raise TimeoutError("couldn't get a connection after 1.0 sec")
    monkeypatch.setattr(calls, "connection", no_pool)
    assert gw.verify(tx)["status"] == "success"
    assert _rows(tx) == []


def test_describe_paths_and_references():
    d = calls.describe
    assert d("POST", "/refund/cn-abc", data={"reference": "rf-123", "amount": "10"}) == {
        "operation": "refund", "method": "POST", "path": "/refund/{tx_ref}", "reference": "rf-123"}
    assert d("GET", "/banks?secret=x")["path"] == "/banks"
    assert d("GET", "/transfers/verify/po-1")["reference"] == "po-1"
    other = d("GET", "/accounts/1000123456789/balance?key=abc")
    assert other["operation"] == "other" and "1000123456789" not in other["path"] and "key" not in other["path"]
    assert d("GET", "/transaction/verify/bad'ref;drop")["reference"] == "badrefdrop"
    assert len(calls.clean_error("x" * 2000)) == 500


# ---------------------------------------------------------------- status and summary


@pytest.fixture
def fake_gw():
    """A private gateway name, so these rows never mix with other tests' Chapa calls."""
    name = f"test-{uuid.uuid4().hex[:10]}"

    def add(minutes_ago=1, *, ok=True, status=200, uncertain=False, ms=300, operation="verify", error=None,
            reference=None):
        execute(
            "insert into gateway_calls (gateway, operation, method, path, reference, http_status, ok, uncertain, error, "
            "duration_ms, created_at) values (%s, %s, 'GET', '/x', %s, %s, %s, %s, %s, %s, "
            "now() - make_interval(mins => %s))",
            (name, operation, reference, status, ok, uncertain, error if not ok else None, ms, minutes_ago),
        )
    add.name = name
    yield add
    execute("delete from gateway_calls where gateway = %s", (name,))


def _status(gw):
    return health.status(gateway=gw.name)


def test_no_calls_yet(fake_gw):
    s = _status(fake_gw)
    assert s["status"] == "no_calls" and s["label"] == "No calls yet" and "No calls" in s["reason"]


def test_healthy_when_chapa_answers(fake_gw):
    for i in range(10):
        fake_gw(i + 1)
    fake_gw(5, ok=False, status=None, uncertain=True, error="No answer from Chapa (ReadTimeout)")  # 1 of 11
    s = _status(fake_gw)
    assert s["status"] == "healthy" and "11 calls in the last hour" in s["reason"]


def test_down_when_nothing_worked_for_30_minutes(fake_gw):
    fake_gw(45)  # worked, but too long ago
    fake_gw(10, ok=False, status=None, uncertain=True, error="No answer from Chapa (ConnectError)")
    fake_gw(3, ok=False, status=502, uncertain=True, error="Bad gateway")
    s = _status(fake_gw)
    assert s["status"] == "down"
    assert "30 minutes" in s["reason"] and "2 calls failed" in s["reason"] and "HTTP 502: Bad gateway" in s["reason"]


def test_a_rejected_key_counts_as_down(fake_gw):
    fake_gw(2, ok=False, status=401, error="Invalid API Key")
    s = _status(fake_gw)
    assert s["status"] == "down" and "Invalid API Key" in s["reason"]


def test_clear_refusals_alone_are_not_an_outage(fake_gw):
    """A checkout not paid yet or a wrong account number is Chapa working; it must never read as down."""
    for i in range(5):
        fake_gw(i + 1, ok=False, status=400, error="Transaction not paid yet")
    s = _status(fake_gw)
    assert s["status"] == "healthy" and "said no to 5" in s["reason"]


def test_degraded_over_20_percent_faults(fake_gw):
    for i in range(3):
        fake_gw(i + 1)
    fake_gw(20, ok=False, status=None, uncertain=True, error="No answer from Chapa (ReadTimeout)")  # 1 of 4 = 25%
    s = _status(fake_gw)
    assert s["status"] == "degraded" and "25%" in s["reason"] and "(1 of 4)" in s["reason"]


def test_exactly_20_percent_is_not_degraded(fake_gw):
    for i in range(4):
        fake_gw(i + 1)
    fake_gw(20, ok=False, status=500, uncertain=True, error="Server error")  # 1 of 5 = 20%
    assert _status(fake_gw)["status"] == "healthy"


def test_degraded_when_slow(fake_gw):
    for i in range(20):
        fake_gw(i + 1, ms=9000)
    s = _status(fake_gw)
    assert s["status"] == "degraded" and "slow" in s["reason"] and "9.0 seconds" in s["reason"]


def test_quiet_hour_follows_the_last_call(fake_gw):
    fake_gw(180)
    s = _status(fake_gw)
    assert s["status"] == "healthy" and s["reason"].startswith("Quiet")
    fake_gw(120, ok=False, status=None, uncertain=True, error="No answer from Chapa (ReadTimeout)")
    s = _status(fake_gw)
    assert s["status"] == "degraded" and "last call failed" in s["reason"]


def test_summary_per_operation(fake_gw):
    fake_gw(5, ms=100)
    fake_gw(4, ms=200)
    fake_gw(3, ms=300)
    fake_gw(2, ok=False, status=400, ms=400, error="Transaction not found")
    fake_gw(10, operation="transfer", ok=False, status=None, uncertain=True, ms=15000, error="No answer from Chapa")
    fake_gw(60 * 30, operation="banks")  # 30 hours ago: outside the 24 hour period
    out = health.summary(24, gateway=fake_gw.name)
    ops = {o["operation"]: o for o in out["operations"]}
    v = ops["verify"]
    assert (v["calls"], v["failures"], v["faults"], v["refusals"]) == (4, 1, 0, 1)
    assert v["failure_rate"] == 0.25 and v["avg_ms"] == 250 and v["p95_ms"] == 385  # 300 + 0.85 * 100
    assert v["last_failure_message"] == "Transaction not found" and v["last_failure_http_status"] == 400
    assert v["last_success_at"] is not None
    t = ops["transfer"]
    assert t["faults"] == 1 and t["uncertain"] == 1 and t["failure_rate"] == 1.0 and t["last_success_at"] is None
    b = ops["banks"]  # not used in the period, but its last success still shows
    assert b["calls"] == 0 and b["last_success_at"] is not None
    assert out["totals"]["calls"] == 5 and out["totals"]["failures"] == 2 and out["totals"]["failure_rate"] == 0.4
    one_hour = health.summary(1, gateway=fake_gw.name)
    assert one_hour["totals"]["calls"] == 5


# ---------------------------------------------------------------- errors and attention


def test_recent_errors_newest_first_and_linked(client, make_user, fake_gw):
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 100)
    pay = fetch_one("select id::text, tx_ref, engagement_id::text from payments where tx_ref = %s", (job["tx"],))
    refund_ref = _ref("rf")
    refund = fetch_one("insert into refunds (payment_id, engagement_id, reference, amount, reason, method, status, "
                       "gateway_ref) values (%s, %s, %s, 10, 'test', 'gateway', 'processing', %s) returning id::text",
                       (pay["id"], pay["engagement_id"], refund_ref, "CHAPA-RF-1"))
    fake_gw(50, ok=False, status=400, operation="verify", reference=job["tx"], error="Transaction not paid")
    fake_gw(40, ok=False, status=None, uncertain=True, operation="transfer", reference=payout["reference"],
            error="No answer from Chapa (ReadTimeout)")
    fake_gw(30, ok=False, status=503, uncertain=True, operation="verify_refund", reference="CHAPA-RF-1", error="busy")
    fake_gw(20, ok=False, status=404, operation="banks", error="Not found")
    fake_gw(10)  # a success is never an error
    try:
        _check_recent_errors(fake_gw, job, payout, pay, refund)
    finally:
        # Left behind, the automatic refund and payout checks in other tests would pick these up
        execute("delete from refunds where id = %s", (refund["id"],))
        execute("delete from payouts where id = %s", (payout["id"],))


def _check_recent_errors(fake_gw, job, payout, pay, refund):
    out = health.recent_errors(10, 0, gateway=fake_gw.name)
    assert out["total"] == 4
    ops = [e["operation"] for e in out["items"]]
    assert ops == ["banks", "verify_refund", "transfer", "verify"]
    banks, refund_err, transfer, verify = out["items"]
    assert banks["belongs_to"] is None and banks["http_status"] == 404 and not banks["fault"]
    assert refund_err["belongs_to"] == {"kind": "refund", "id": refund["id"], "tx_ref": job["tx"], "status": "processing"}
    assert refund_err["uncertain"] and refund_err["fault"]
    assert transfer["belongs_to"]["kind"] == "payout" and transfer["belongs_to"]["id"] == payout["id"]
    assert transfer["uncertain"] and transfer["http_status"] is None
    assert verify["belongs_to"] == {"kind": "payment", "id": pay["id"], "tx_ref": job["tx"],
                                    "engagement_id": pay["engagement_id"], "status": "success"}
    assert verify["error"] == "Transaction not paid"
    page = health.recent_errors(2, 2, gateway=fake_gw.name)
    assert [e["operation"] for e in page["items"]] == ["transfer", "verify"] and page["total"] == 4


def test_attention_lists_stuck_payments_unconfirmed_payouts_and_failed_refunds(client, make_user):
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 200)
    note = "The transfer request got an error: timeout. The money stays held. Use Check with Chapa."
    execute("update payouts set status = 'approved', needs_check = true, check_note = %s, decided_at = now() "
            "where id = %s", (note, payout["id"]))
    pay = fetch_one("select id, engagement_id from payments where tx_ref = %s", (job["tx"],))
    stuck_tx, fresh_tx = _ref("cn-stuck"), _ref("cn-fresh")
    for tx, minutes in ((stuck_tx, 45), (fresh_tx, 5)):
        execute("insert into payments (engagement_id, tx_ref, gateway, amount, commission_percent, commission_amount, "
                "provider_amount, status, created_at) values (%s, %s, 'simulated', 1150, 10, 100, 900, 'pending', "
                "now() - make_interval(mins => %s))", (pay["engagement_id"], tx, minutes))
    execute("insert into gateway_calls (gateway, operation, method, path, reference, http_status, ok, error) "
            "values ('chapa', 'verify', 'GET', '/transaction/verify/{ref}', %s, 400, false, 'Transaction not paid')",
            (stuck_tx,))
    failed_ref, old_ref = _ref("rf"), _ref("rf-old")
    for ref, days in ((failed_ref, 0), (old_ref, 10)):
        execute("insert into refunds (payment_id, engagement_id, reference, amount, reason, method, status, error, "
                "updated_at) values (%s, %s, %s, 75, 'test', 'gateway', 'failed', %s, now() - make_interval(days => %s))",
                (pay["id"], pay["engagement_id"], ref, "Chapa refused the refund: insufficient balance", days))
    try:
        items = health.attention()["items"]
        mine = {i["reference"]: i for i in items}
        p = mine[payout["reference"]]
        assert p["kind"] == "payout" and p["problem"] == "needs_check" and p["amount"] == 200.0 and p["reason"] == note
        r = mine[failed_ref]
        assert r["kind"] == "refund" and r["problem"] == "failed" and r["amount"] == 75.0
        assert r["reason"] == "Chapa refused the refund: insufficient balance" and r["tx_ref"] == job["tx"]
        s = mine[stuck_tx]
        assert s["kind"] == "payment" and s["problem"] == "stuck" and s["amount"] == 1150.0
        assert s["age_seconds"] >= 45 * 60 and "Transaction not paid" in s["reason"]
        assert fresh_tx not in mine and old_ref not in mine
        # Most urgent first: money that may have moved, then failures, then stuck checkouts
        order = [i["reference"] for i in items if i["reference"] in (payout["reference"], failed_ref, stuck_tx)]
        assert order == [payout["reference"], failed_ref, stuck_tx]
        assert payout["reference"] not in {i["reference"] for i in health.attention(include_payouts=False)["items"]}
        # Once settled it leaves the list
        execute("update payouts set status = 'paid', needs_check = false where id = %s", (payout["id"],))
        assert payout["reference"] not in {i["reference"] for i in health.attention()["items"]}
    finally:
        execute("delete from gateway_calls where reference = %s", (stuck_tx,))
        execute("delete from payments where tx_ref in (%s, %s)", (stuck_tx, fresh_tx))
        execute("delete from refunds where reference in (%s, %s)", (failed_ref, old_ref))
        execute("delete from payouts where id = %s", (payout["id"],))


def test_failed_payout_in_the_last_week_is_listed(client, make_user):
    job = _paid_job(client, make_user)
    _payout_account(client, job["agent"])
    payout = _request_payout(client, job["agent"], 100)
    execute("update payouts set status = 'failed', check_note = 'Chapa reports the transfer failed', "
            "decided_at = now() - interval '2 days' where id = %s", (payout["id"],))
    try:
        item = {i["reference"]: i for i in health.attention()["items"]}[payout["reference"]]
        assert item["problem"] == "failed" and item["reason"] == "Chapa reports the transfer failed"
        execute("update payouts set decided_at = now() - interval '8 days' where id = %s", (payout["id"],))
        assert payout["reference"] not in {i["reference"] for i in health.attention()["items"]}
    finally:
        execute("delete from payouts where id = %s", (payout["id"],))


def test_prune_keeps_90_days():
    name = f"test-{uuid.uuid4().hex[:10]}"
    for days in (100, 10):
        execute("insert into gateway_calls (gateway, operation, method, path, ok, created_at) "
                "values (%s, 'banks', 'GET', '/banks', true, now() - make_interval(days => %s))", (name, days))
    try:
        assert payment_service.prune_gateway_calls() >= 1
        left = fetch_all("select extract(day from now() - created_at)::int as d from gateway_calls where gateway = %s",
                         (name,))
        assert [r["d"] for r in left] == [10]
    finally:
        execute("delete from gateway_calls where gateway = %s", (name,))


# ---------------------------------------------------------------- live check and endpoints


def test_live_check_skips_the_bank_cache_and_is_recorded(chapa, monkeypatch):
    from services.payment_service import payout_account

    monkeypatch.setattr(settings, "payments_mode", "chapa")
    monkeypatch.setitem(payout_account._banks_cache, "chapa", (10 ** 12, [{"code": "1", "name": "Cached"}]))
    chapa(lambda m, u, **kw: Answer(200, {"data": [{"id": 1, "name": "CBE"}, {"id": 2, "name": "Awash"}]}))
    before = fetch_one("select coalesce(max(id), 0) as id from gateway_calls")["id"]
    out = health.live_check()
    assert out["ok"] is True and out["http_status"] == 200 and out["latency_ms"] >= 0 and "2 banks" in out["message"]
    assert len(chapa.sent) == 1 and chapa.sent[0][1].endswith("/banks")
    rows = fetch_all("select * from gateway_calls where id > %s and operation = 'banks' and ok", (before,))
    assert rows
    execute("delete from gateway_calls where id = any(%s)", ([r["id"] for r in rows],))

    chapa(lambda m, u, **kw: Answer(503, {"message": "Service unavailable"}))
    out = health.live_check()
    assert out["ok"] is False and out["http_status"] == 503 and out["uncertain"] and "Service unavailable" in out["error"]
    execute("delete from gateway_calls where id > %s and operation = 'banks'", (before,))


def test_live_check_in_simulated_mode_says_so():
    out = health.live_check()
    assert out["ok"] is None and out["simulated"] is True and "simulated" in out["message"]


def test_payment_health_endpoints(client, make_staff):
    admin = make_staff()
    r = client.get(f"{API}/admin/marketplace/payment-health?hours=1", headers=admin["headers"])
    assert r.status_code == 200, r.text
    body = r.json()["payload"]
    assert body["status"]["status"] in ("no_calls", "healthy", "degraded", "down") and body["status"]["reason"]
    assert body["summary"]["hours"] == 1 and "items" in body["attention"]
    assert client.get(f"{API}/admin/marketplace/payment-health?hours=0", headers=admin["headers"]).status_code == 422
    r = client.get(f"{API}/admin/marketplace/payment-health/errors?limit=5&offset=0", headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["limit"] == 5
    r = client.post(f"{API}/admin/marketplace/payment-health/check", headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["simulated"] is True


def test_payment_health_needs_payments_view(client, make_staff, make_user):
    support = make_staff("support_agent")  # no payments.view
    for method, path in (("get", "payment-health"), ("get", "payment-health/errors"), ("post", "payment-health/check")):
        r = getattr(client, method)(f"{API}/admin/marketplace/{path}", headers=support["headers"])
        assert r.status_code == 403, (path, r.text)
    finance = make_staff("finance")
    assert client.get(f"{API}/admin/marketplace/payment-health", headers=finance["headers"]).status_code == 200
    user = make_user()
    assert client.get(f"{API}/admin/marketplace/payment-health", headers=user["headers"]).status_code in (401, 403)
