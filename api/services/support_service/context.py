"""What staff see about the customer behind a ticket."""

from __future__ import annotations

from services.db import fetch_all, fetch_one
from .common import STATUS_LABELS, _is_uuid, queue_label


# ---------------------------------------------------------------- customer context


def customer_context(ticket_id: str, *, can=None) -> dict | None:
    """What staff need to know about the person behind a ticket: their account, hires, payments and
    other requests. Hires and payments are left out for staff without those permissions. No ID numbers,
    addresses, payout details or gateway data."""
    can = can or (lambda _permission: True)
    t = fetch_one("select id::text, user_id::text, contact_phone, contact_email from support_tickets where id = %s",
                  (ticket_id,)) if _is_uuid(ticket_id) else None
    if not t:
        return None
    out: dict = {"account": None, "provider": None, "hires": None, "payments": None, "hidden": []}
    uid = t["user_id"]
    if uid:
        out["account"] = fetch_one(
            """
            select u.id::text, coalesce(nullif(u.fullname, ''), u.email) as name, u.email, u.phone, u.role, u.is_active,
                   u.created_at, u.last_login_at,
                   (select count(*) from roadmaps r where r.user_id = u.id) as roadmaps
            from users u where u.id = %s
            """,
            (uid,),
        )
        out["provider"] = fetch_one(
            "select id::text, display_name, status, provider_type from providers where user_id = %s limit 1", (uid,))
        if can("hires.view"):
            out["hires"] = {
                "items": fetch_all(
                    """
                    select e.id::text, coalesce(nullif(e.title, ''), e.service_name, 'Hire') as title, e.status,
                           e.payment_status, e.disputed, e.dispute_status, e.agreed_price, e.created_at,
                           p.display_name as provider_name
                    from engagements e left join providers p on p.id = e.provider_id
                    where e.client_user_id = %s and not coalesce(e.is_sample, false)
                    order by e.created_at desc limit 5
                    """,
                    (uid,),
                ),
                "total": fetch_one("select count(*) as c from engagements where client_user_id = %s "
                                   "and not coalesce(is_sample, false)", (uid,))["c"],
            }
        else:
            out["hidden"].append("hires")
        if can("payments.view"):
            out["payments"] = {
                "items": fetch_all(
                    """
                    select p.tx_ref, p.amount, p.currency, p.status, p.created_at, p.verified_at,
                           coalesce(nullif(e.title, ''), e.service_name) as hire_title
                    from payments p left join engagements e on e.id = p.engagement_id
                    where p.payer_user_id = %s order by p.created_at desc limit 5
                    """,
                    (uid,),
                ),
                "total": fetch_one("select count(*) as c from payments where payer_user_id = %s", (uid,))["c"],
            }
        else:
            out["hidden"].append("payments")
        other, params = "t.user_id = %(uid)s", {"uid": uid}
    else:
        # No account: other requests left with the same phone or email
        conds, params = [], {}
        if t["contact_phone"]:
            conds.append("t.contact_phone = %(phone)s")
            params["phone"] = t["contact_phone"]
        if t["contact_email"]:
            conds.append("lower(t.contact_email) = lower(%(email)s)")
            params["email"] = t["contact_email"]
        other = f"({' or '.join(conds)})" if conds else "false"
    params["id"] = t["id"]
    out["tickets"] = {
        "items": fetch_all(
            f"""
            select t.id::text, t.ref, t.subject, t.status, t.queue, t.created_at from support_tickets t
            where {other} and t.id <> %(id)s order by t.created_at desc limit 5
            """,
            params,
        ),
        "total": fetch_one(f"select count(*) as c from support_tickets t where {other} and t.id <> %(id)s", params)["c"],
    }
    for item in out["tickets"]["items"]:
        item["status_label"] = STATUS_LABELS[item["status"]]
        item["queue_label"] = queue_label(item["queue"])
    return out
