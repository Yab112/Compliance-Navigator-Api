"""Payment health for staff: how Chapa is answering, what went wrong, and money that needs a person.

Every Chapa call is recorded in gateway_calls (calls.py). A failed call is one of two kinds:
  - a fault: Chapa did not answer (timeout, connection error), answered with a server error (5xx),
    refused our key (401, 403) or asked us to slow down (429). These say Chapa is not working for us.
  - a refusal: any other 4xx answer. Chapa is working; it said no to this one request (for example a
    wrong account number, or a checkout that was never paid).
The status only looks at faults, so a quiet hour of "not paid yet" answers never reads as an outage.

Status rules (checked in this order):
  no_calls  nothing recorded yet
  down      no successful call in the last 30 minutes while at least one call there was a fault
  degraded  over 20% of the calls in the last hour were faults, or the slowest 5% took over 8 seconds,
            or there were no calls in the last hour and the last call was a fault
  healthy   otherwise
"""

from __future__ import annotations

import time

from services import payment_service
from services.db import fetch_all, fetch_one

from .gateways import PaymentError, mode

DOWN_MINUTES = 30
DEGRADED_MINUTES = 60
DEGRADED_FAULT_RATE = 0.20
SLOW_P95_MS = 8000
STUCK_PAYMENT_MINUTES = 30
RECENT_DAYS = 7

# A failed call that says Chapa is not working for us (see the module docstring)
FAULT = "(not c.ok and (c.uncertain or c.http_status is null or c.http_status >= 500 or c.http_status in (401, 403, 429)))"
REFUSAL = f"(not c.ok and not {FAULT})"

STATUS_LABELS = {"no_calls": "No calls yet", "healthy": "Healthy", "degraded": "Degraded", "down": "Down"}


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def _ms(value) -> int | None:
    return None if value is None else round(float(value))


def summary(hours: int = 24, *, gateway: str = "chapa") -> dict:
    """Per operation for the last `hours`: calls, failures (faults and refusals), failure rate, average and
    p95 latency; with the last success and the last failure (and its message) over everything kept."""
    window = fetch_all(
        f"""
        select c.operation, count(*) as calls, count(*) filter (where not c.ok) as failures,
               count(*) filter (where {FAULT}) as faults, count(*) filter (where {REFUSAL}) as refusals,
               count(*) filter (where not c.ok and c.uncertain) as uncertain,
               avg(c.duration_ms) as avg_ms, percentile_cont(0.95) within group (order by c.duration_ms) as p95_ms
        from gateway_calls c
        where c.gateway = %s and c.created_at > now() - make_interval(hours => %s)
        group by c.operation
        """,
        (gateway, hours),
    )
    lasts = fetch_all(
        """
        select o.operation,
               (select max(created_at) from gateway_calls where gateway = %s and operation = o.operation and ok)
                 as last_success_at,
               f.created_at as last_failure_at, f.error as last_failure_message, f.http_status as last_failure_http_status
        from (select distinct operation from gateway_calls where gateway = %s) o
        left join lateral (
          select created_at, error, http_status from gateway_calls
          where gateway = %s and operation = o.operation and not ok order by created_at desc, id desc limit 1
        ) f on true
        """,
        (gateway, gateway, gateway),
    )
    by_op = {r["operation"]: r for r in lasts}
    operations = []
    for r in window:
        last = by_op.get(r["operation"], {})
        operations.append({
            "operation": r["operation"], "calls": r["calls"], "failures": r["failures"], "faults": r["faults"],
            "refusals": r["refusals"], "uncertain": r["uncertain"], "failure_rate": _rate(r["failures"], r["calls"]),
            "avg_ms": _ms(r["avg_ms"]), "p95_ms": _ms(r["p95_ms"]),
            "last_success_at": last.get("last_success_at"), "last_failure_at": last.get("last_failure_at"),
            "last_failure_message": last.get("last_failure_message"),
            "last_failure_http_status": last.get("last_failure_http_status"),
        })
    # Operations used before but not in this period still show when they last worked or failed
    for op, last in by_op.items():
        if op not in {o["operation"] for o in operations}:
            operations.append({
                "operation": op, "calls": 0, "failures": 0, "faults": 0, "refusals": 0, "uncertain": 0,
                "failure_rate": 0.0, "avg_ms": None, "p95_ms": None, "last_success_at": last["last_success_at"],
                "last_failure_at": last["last_failure_at"], "last_failure_message": last["last_failure_message"],
                "last_failure_http_status": last["last_failure_http_status"],
            })
    operations.sort(key=lambda o: (-o["calls"], o["operation"]))
    totals = fetch_one(
        f"""
        select count(*) as calls, count(*) filter (where not c.ok) as failures, count(*) filter (where {FAULT}) as faults,
               count(*) filter (where {REFUSAL}) as refusals, count(*) filter (where c.is_test) as test_calls,
               avg(c.duration_ms) as avg_ms, percentile_cont(0.95) within group (order by c.duration_ms) as p95_ms
        from gateway_calls c where c.gateway = %s and c.created_at > now() - make_interval(hours => %s)
        """,
        (gateway, hours),
    )
    return {
        "hours": hours, "operations": operations,
        "totals": {"calls": totals["calls"], "failures": totals["failures"], "faults": totals["faults"],
                   "refusals": totals["refusals"], "test_calls": totals["test_calls"],
                   "failure_rate": _rate(totals["failures"], totals["calls"]),
                   "avg_ms": _ms(totals["avg_ms"]), "p95_ms": _ms(totals["p95_ms"])},
    }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def status(*, gateway: str = "chapa") -> dict:
    """healthy, degraded, down or no_calls, with the reason in plain words (rules in the module docstring)."""
    row = fetch_one(
        f"""
        select count(*) filter (where c.created_at > now() - make_interval(mins => %(down)s) and c.ok) as ok_down,
               count(*) filter (where c.created_at > now() - make_interval(mins => %(down)s) and {FAULT}) as faults_down,
               count(*) filter (where c.created_at > now() - make_interval(mins => %(deg)s)) as calls_hour,
               count(*) filter (where c.created_at > now() - make_interval(mins => %(deg)s) and {FAULT}) as faults_hour,
               count(*) filter (where c.created_at > now() - make_interval(mins => %(deg)s) and {REFUSAL}) as refusals_hour,
               percentile_cont(0.95) within group (order by c.duration_ms)
                 filter (where c.created_at > now() - make_interval(mins => %(deg)s)) as p95_hour,
               max(c.created_at) filter (where c.ok) as last_success_at,
               max(c.created_at) as last_call_at
        from gateway_calls c where c.gateway = %(gw)s
        """,
        {"down": DOWN_MINUTES, "deg": DEGRADED_MINUTES, "gw": gateway},
    )
    last_call = fetch_one(
        f"select c.ok, {FAULT} as fault, c.error, c.http_status, c.created_at from gateway_calls c "
        "where c.gateway = %s order by c.created_at desc, c.id desc limit 1", (gateway,))
    last_fault = fetch_one(
        f"select c.error, c.http_status, c.operation, c.created_at from gateway_calls c where c.gateway = %s and {FAULT} "
        "order by c.created_at desc, c.id desc limit 1", (gateway,))
    out = {"mode": mode(), "last_success_at": row["last_success_at"], "last_call_at": row["last_call_at"],
           "last_fault": last_fault, "calls_last_hour": row["calls_hour"], "faults_last_hour": row["faults_hour"],
           "refusals_last_hour": row["refusals_hour"], "p95_ms_last_hour": _ms(row["p95_hour"])}

    def said(fault: dict | None) -> str:
        if not fault:
            return ""
        code = f"HTTP {fault['http_status']}: " if fault.get("http_status") else ""
        return f" Last error: {code}{fault.get('error') or 'no message'}."

    if not last_call:
        state, reason = "no_calls", "No calls to Chapa recorded yet."
    elif row["ok_down"] == 0 and row["faults_down"] > 0:
        state = "down"
        reason = (f"No successful call to Chapa in the last {DOWN_MINUTES} minutes, and "
                  f"{_plural(row['faults_down'], 'call')} failed without a clear answer.{said(last_fault)}")
    elif row["calls_hour"] and _rate(row["faults_hour"], row["calls_hour"]) > DEGRADED_FAULT_RATE:
        state = "degraded"
        reason = (f"{round(100 * row['faults_hour'] / row['calls_hour'])}% of calls in the last hour failed without a "
                  f"clear answer ({row['faults_hour']} of {row['calls_hour']}).{said(last_fault)}")
    elif row["calls_hour"] and row["p95_hour"] is not None and float(row["p95_hour"]) > SLOW_P95_MS:
        state = "degraded"
        reason = (f"Chapa is slow: the slowest 5% of calls in the last hour took over "
                  f"{float(row['p95_hour']) / 1000:.1f} seconds (over {SLOW_P95_MS // 1000} seconds counts as slow).")
    elif not row["calls_hour"] and last_call["fault"]:
        state = "degraded"
        reason = f"No calls in the last hour, and the last call failed without a clear answer.{said(last_call)}"
    elif row["calls_hour"]:
        state = "healthy"
        reason = f"Chapa is answering normally: {_plural(row['calls_hour'], 'call')} in the last hour."
        if row["refusals_hour"]:
            reason += (f" Chapa said no to {row['refusals_hour']} of them (for example a checkout not paid yet); "
                       "see Recent errors.")
    else:
        state = "healthy"
        reason = "Quiet: no calls in the last hour. The last call got a clear answer from Chapa."
    out.update({"status": state, "label": STATUS_LABELS[state], "reason": reason})
    return out


def recent_errors(limit: int = 25, offset: int = 0, *, gateway: str = "chapa") -> dict:
    """Failed calls, newest first, each with what its reference belongs to (payment, payout or refund)."""
    rows = fetch_all(
        f"""
        select c.id, c.created_at, c.operation, c.method, c.path, c.reference, c.http_status, c.error, c.uncertain,
               c.is_test, c.duration_ms, {FAULT} as fault,
               p.id::text as payment_id, p.tx_ref as payment_tx_ref, p.engagement_id::text as payment_engagement_id,
               p.status as payment_status,
               po.id::text as payout_id, po.status as payout_status,
               r.id::text as refund_id, r.status as refund_status, rp.tx_ref as refund_tx_ref
        from gateway_calls c
        left join payments p on c.operation in ('initialize', 'verify') and p.tx_ref = c.reference
        left join payouts po on c.operation in ('transfer', 'verify_transfer') and po.reference = c.reference
        left join lateral (
          select id, status, payment_id from refunds
          where c.operation in ('refund', 'verify_refund') and (reference = c.reference or gateway_ref = c.reference)
          order by created_at desc limit 1
        ) r on true
        left join payments rp on rp.id = r.payment_id
        where c.gateway = %s and not c.ok
        order by c.created_at desc, c.id desc limit %s offset %s
        """,
        (gateway, limit, offset),
    )
    total = fetch_one("select count(*) as c from gateway_calls where gateway = %s and not ok", (gateway,))["c"]
    items = []
    for r in rows:
        if r["payment_id"]:
            belongs = {"kind": "payment", "id": r["payment_id"], "tx_ref": r["payment_tx_ref"],
                       "engagement_id": r["payment_engagement_id"], "status": r["payment_status"]}
        elif r["payout_id"]:
            belongs = {"kind": "payout", "id": r["payout_id"], "status": r["payout_status"]}
        elif r["refund_id"]:
            belongs = {"kind": "refund", "id": r["refund_id"], "tx_ref": r["refund_tx_ref"], "status": r["refund_status"]}
        else:
            belongs = None
        items.append({
            "id": r["id"], "created_at": r["created_at"], "operation": r["operation"], "method": r["method"],
            "path": r["path"], "reference": r["reference"], "http_status": r["http_status"], "error": r["error"],
            "uncertain": r["uncertain"], "fault": r["fault"], "is_test": r["is_test"], "duration_ms": r["duration_ms"],
            "belongs_to": belongs,
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def attention(*, include_payouts: bool = True, limit: int = 50) -> dict:
    """
    Money that needs a person now, most urgent first:
      - payouts approved but not confirmed (needs_check: the money may have left), and payouts that failed
        in the last 7 days
      - refunds that need checking with Chapa, and refunds that failed in the last 7 days
      - payments still pending 30 minutes after the checkout started
    Each with its amount, its age in seconds and the stored reason.
    """
    items: list[dict] = []
    if include_payouts:
        for r in fetch_all(
            """
            select po.id::text, po.reference, po.status, po.needs_check, po.amount::float, po.check_note, po.is_test,
                   coalesce(po.decided_at, po.created_at) as since, pr.display_name as provider_name,
                   extract(epoch from now() - coalesce(po.decided_at, po.created_at))::int as age_seconds
            from payouts po left join providers pr on pr.id = po.provider_id
            where (po.status = 'approved' and po.needs_check)
               or (po.status = 'failed' and coalesce(po.decided_at, po.created_at) > now() - make_interval(days => %s))
            order by po.needs_check desc, since limit %s
            """,
            (RECENT_DAYS, limit),
        ):
            check = r["status"] == "approved"
            items.append({
                "kind": "payout", "id": r["id"], "reference": r["reference"], "status": r["status"],
                "problem": "needs_check" if check else "failed", "amount": r["amount"], "since": r["since"],
                "age_seconds": r["age_seconds"], "is_test": r["is_test"], "who": r["provider_name"],
                "reason": r["check_note"] or ("The transfer could not be confirmed. Check with Chapa." if check
                                              else "The transfer failed."),
            })
    for r in fetch_all(
        """
        select r.id::text, r.reference, r.status, r.amount::float, r.error, r.note, r.is_test, r.method,
               case when r.status = 'failed' then r.updated_at else r.created_at end as since, p.tx_ref,
               e.client_name,
               extract(epoch from now() - case when r.status = 'failed' then r.updated_at else r.created_at end)::int
                 as age_seconds
        from refunds r join payments p on p.id = r.payment_id left join engagements e on e.id = r.engagement_id
        where r.status = 'needs_check'
           or (r.status = 'failed' and r.updated_at > now() - make_interval(days => %s))
        order by (r.status = 'needs_check') desc, since limit %s
        """,
        (RECENT_DAYS, limit),
    ):
        check = r["status"] == "needs_check"
        items.append({
            "kind": "refund", "id": r["id"], "reference": r["reference"], "tx_ref": r["tx_ref"], "status": r["status"],
            "problem": "needs_check" if check else "failed", "amount": r["amount"], "since": r["since"],
            "age_seconds": r["age_seconds"], "is_test": r["is_test"], "who": r["client_name"],
            "reason": r["error"] or r["note"] or ("Chapa's answer was lost. Check with Chapa." if check
                                                  else "The refund failed."),
        })
    for r in fetch_all(
        """
        select p.id::text, p.tx_ref, p.amount::float, p.created_at as since, p.is_test, p.engagement_id::text,
               e.client_name, extract(epoch from now() - p.created_at)::int as age_seconds,
               (select c.error from gateway_calls c where c.reference = p.tx_ref and not c.ok
                order by c.created_at desc, c.id desc limit 1) as last_error
        from payments p join engagements e on e.id = p.engagement_id
        where p.status = 'pending' and p.created_at < now() - make_interval(mins => %s)
        order by p.created_at limit %s
        """,
        (STUCK_PAYMENT_MINUTES, limit),
    ):
        reason = ("Still pending after 30 minutes. Usually the client left the checkout; it is checked with Chapa "
                  "every 15 minutes and cancelled after 3 days.")
        if r["last_error"]:
            reason += f" Last error: {r['last_error']}"
        items.append({
            "kind": "payment", "id": r["id"], "reference": r["tx_ref"], "tx_ref": r["tx_ref"], "status": "pending",
            "problem": "stuck", "amount": r["amount"], "since": r["since"], "age_seconds": r["age_seconds"],
            "is_test": r["is_test"], "who": r["client_name"], "engagement_id": r["engagement_id"], "reason": reason,
        })
    rank = {"needs_check": 0, "failed": 1, "stuck": 2}
    items.sort(key=lambda i: (rank[i["problem"]], -i["age_seconds"]))
    return {"items": items, "total": len(items)}


def overview(hours: int = 24, *, include_payouts: bool = True) -> dict:
    return {"status": status(), "summary": summary(hours), "attention": attention(include_payouts=include_payouts)}


def live_check() -> dict:
    """One cheap call to Chapa (the bank list, never the cached copy), recorded like any other call."""
    current = mode()
    if current != "chapa":
        message = ("Payments are in test mode (simulated): nothing is sent to Chapa, so there is nothing to check."
                   if current == "simulated" else "Online payments are off, so nothing is sent to Chapa.")
        return {"ok": None, "simulated": current == "simulated", "mode": current, "latency_ms": None,
                "http_status": None, "error": None, "message": message}
    started = time.monotonic()
    try:
        gw = payment_service.gateway()
        banks = gw.banks()
    except PaymentError as exc:
        return {"ok": False, "simulated": False, "mode": current, "latency_ms": round((time.monotonic() - started) * 1000),
                "http_status": exc.gateway_status, "uncertain": exc.uncertain, "error": str(exc),
                "message": "Chapa did not answer properly."}
    latency = round((time.monotonic() - started) * 1000)
    return {"ok": True, "simulated": False, "mode": current, "latency_ms": latency,
            "http_status": getattr(gw, "last_status", None), "error": None,
            "message": f"Chapa answered in {latency / 1000:.1f} seconds with {_plural(len(banks), 'bank')}."}
