"""Staff views of client payments: list, CSV export and re-checking with the gateway."""

from __future__ import annotations

from services import payment_service, platform_settings
from services.db import fetch_all, fetch_one

from .earnings import _test_money
from .gateways import PaymentError, mode

# ---------------------------------------------------------------- staff

ADMIN_PAYMENT_SELECT = """
  select p.tx_ref, p.gateway, p.amount::float, p.currency, p.price::float, p.provider_vat::float,
         p.commission_amount::float, p.commission_vat::float, p.provider_amount::float, p.gateway_fee::float,
         p.status, p.payment_method, p.gateway_reference, p.created_at, p.verified_at, p.is_test, p.unapplied_reason,
         p.refunded_amount::float, (p.amount - p.refunded_amount)::float as refundable,
         e.id::text as engagement_id, e.title, e.client_name, e.refund_needed, e.payment_status as hire_payment_status,
         pr.display_name as provider_name, pr.slug as provider_slug,
         (select count(*) from refunds r where r.payment_id = p.id and r.status not in ('failed', 'refunded'))
           as refunds_open
  from payments p join engagements e on e.id = p.engagement_id left join providers pr on pr.id = e.provider_id
"""


def _admin_filters(status: str | None, q: str | None, date_from, date_to, needs_refund: bool | None,
                   engagement_id: str | None = None) -> tuple[list[str], list]:
    where, params = ["true"], []
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append("(p.tx_ref ilike %s or p.gateway_reference ilike %s or e.title ilike %s or e.client_name ilike %s "
                     "or pr.display_name ilike %s)")
        params += [like] * 5
    if date_from:
        where.append("(p.created_at at time zone 'Africa/Addis_Ababa')::date >= %s")
        params.append(date_from)
    if date_to:
        where.append("(p.created_at at time zone 'Africa/Addis_Ababa')::date <= %s")
        params.append(date_to)
    if needs_refund:
        where.append("p.status = 'success' and p.refunded_amount < p.amount and (e.refund_needed or p.unapplied_reason is not null)")
    if engagement_id:
        where.append("e.id::text = %s")
        params.append(engagement_id)
    return where, params


def admin_list(status: str | None = None, limit: int = 50, offset: int = 0, *, q: str | None = None,
               date_from=None, date_to=None, needs_refund: bool | None = None, engagement_id: str | None = None) -> dict:
    """
    Every amount in the tiles, so they add up: gross = price + provider VAT = commission + VAT on commission
    + to providers. Money from extra payments that was not credited to anyone is shown on its own.
    The tiles follow the search and dates but not the status tab. In live mode they leave out test money.
    """
    where, params = _admin_filters(None, q, date_from, date_to, needs_refund, engagement_id)
    listed = where + (["p.status = %s"] if status else [])
    list_params = params + ([status] if status else [])
    joins = "from payments p join engagements e on e.id = p.engagement_id left join providers pr on pr.id = e.provider_id"
    rows = fetch_all(f"{ADMIN_PAYMENT_SELECT} where {' and '.join(listed)} order by p.created_at desc limit %s offset %s",
                     (*list_params, limit, offset))
    total = fetch_one(f"select count(*) as c {joins} where {' and '.join(listed)}", list_params)["c"]
    live = not _test_money()
    tiles = where + (["not p.is_test"] if live else [])
    ok = "p.status = 'success' and p.unapplied_reason is null"
    totals = fetch_one(
        f"""
        select count(*) filter (where {ok}) as paid_count,
               coalesce(sum(p.amount) filter (where {ok}), 0)::float as gross,
               coalesce(sum(p.price) filter (where {ok}), 0)::float as price,
               coalesce(sum(p.provider_vat) filter (where {ok}), 0)::float as provider_vat,
               coalesce(sum(p.commission_amount) filter (where {ok}), 0)::float as commission,
               coalesce(sum(p.commission_vat) filter (where {ok}), 0)::float as commission_vat,
               coalesce(sum(p.provider_amount) filter (where {ok}), 0)::float as to_providers,
               coalesce(sum(p.gateway_fee) filter (where p.status = 'success'), 0)::float as gateway_fees,
               coalesce(sum(p.refunded_amount) filter (where p.status = 'success'), 0)::float as refunded,
               coalesce(sum(p.refunded_commission + p.refunded_commission_vat) filter (where {ok}), 0)::float
                 as commission_refunded,
               coalesce(sum(p.refunded_provider_amount) filter (where {ok}), 0)::float as provider_refunded,
               coalesce(sum(p.amount) filter (where p.status = 'success' and p.unapplied_reason is not null), 0)::float
                 as unapplied,
               count(*) filter (where p.status = 'pending') as pending,
               count(*) filter (where p.status = 'failed') as failed,
               count(*) filter (where p.status = 'success' and p.refunded_amount < p.amount
                                and (e.refund_needed or p.unapplied_reason is not null)) as needs_refund
        {joins} where {' and '.join(tiles)}
        """,
        params,
    )
    totals["net_commission"] = round(totals["commission"] + totals["commission_vat"] - totals["commission_refunded"], 2)
    test_count = fetch_one(f"select count(*) as c {joins} where {' and '.join(where)} and p.is_test", params)["c"] if live else 0
    return {"items": rows, "total": total, "totals": totals, "mode": mode(), "test_mode": _test_money(),
            "test_payments": test_count, "commission_percent": platform_settings.get("commission_percent")}


CSV_COLUMNS = ["tx_ref", "created_at", "verified_at", "status", "gateway", "is_test", "title", "client_name", "provider_name",
               "price", "provider_vat", "amount", "commission_amount", "commission_vat", "provider_amount", "gateway_fee",
               "refunded_amount", "unapplied_reason", "payment_method", "gateway_reference", "engagement_id"]


def admin_csv(status: str | None = None, *, q: str | None = None, date_from=None, date_to=None,
              needs_refund: bool | None = None) -> str:
    import csv
    import io

    where, params = _admin_filters(status, q, date_from, date_to, needs_refund)
    if status:
        where.append("p.status = %s")
        params.append(status)
    rows = fetch_all(f"{ADMIN_PAYMENT_SELECT} where {' and '.join(where)} order by p.created_at desc limit 20000", params)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for r in rows:
        # A cell starting with = + - @ would run as a formula in a spreadsheet
        writer.writerow([("'" + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v
                         for v in (r.get(c) for c in CSV_COLUMNS)])
    return out.getvalue()


def admin_verify(tx_ref: str) -> dict:
    """Staff ask the gateway again about a payment that is still pending (the client never came back)."""
    payment = payment_service.get(tx_ref)
    if not payment:
        raise PaymentError("Payment not found", 404)
    before = payment["status"]
    after = payment_service.confirm(tx_ref)
    return {"payment": after, "changed": after["status"] != before}
