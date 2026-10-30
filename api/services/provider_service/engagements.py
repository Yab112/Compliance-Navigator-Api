"""Engagements (hires): reading, views, notifications, creating and listing."""

from __future__ import annotations

import logging

from services import catalog_service, platform_settings, provider_service
from services.db import execute, fetch_all, fetch_one

from .common import LIVE, PRIVATE_COLUMNS, MarketplaceError, get_for_user
from .trust import recompute

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- engagements (hires)


ENGAGEMENT_COLUMNS = """
  e.id::text, e.client_user_id::text, e.client_name, e.client_phone, e.provider_id::text,
  e.title, e.service_id, e.service_name, e.specialty, e.sub_city, e.details, e.budget, e.status,
  e.admin_note, e.created_at, e.updated_at, e.accepted_at, e.completed_at, e.client_confirmed_at,
  e.declined_reason, e.disputed, e.dispute_reason, e.dispute_status, e.dispute_note,
  p.display_name as provider_name, p.slug as provider_slug, p.phone as provider_phone,
  p.registration_no as provider_registration_no, p.provider_type, p.photo_url as provider_photo_url,
  r.id::text as review_id, r.rating as review_rating,
  e.agreed_price::float, e.price_note, e.payment_status, e.paid_at, e.payment_requested_at,
  coalesce(p.vat_registered, false) as provider_vat_registered,
  (select pay.tx_ref from payments pay where pay.engagement_id = e.id and pay.status = 'success'
     order by pay.verified_at desc nulls last limit 1) as paid_tx_ref,
  e.client_telegram, p.telegram_username as provider_telegram, e.completion_note, e.auto_confirmed,
  r.comment as review_comment, r.reply as review_reply, r.edited_at as review_edited_at,
  cr.rating as client_rating, cr.comment as client_rating_comment,
  (select c.status from review_change_requests c where c.review_id = r.id order by c.created_at desc limit 1)
    as review_change_status,
  e.refund_needed, e.refund_flagged_at, e.refund_flagged_by, e.dispute_resolved_by, e.dispute_resolved_at
"""
# Staff-only fields, removed from what the client and the provider see
STAFF_ONLY = ("admin_note", "refund_needed", "refund_flagged_at", "refund_flagged_by", "dispute_resolved_by")
ENGAGEMENT_FROM = (
    "engagements e left join providers p on p.id = e.provider_id "
    "left join reviews r on r.engagement_id = e.id "
    "left join client_reviews cr on cr.engagement_id = e.id"
)


def get_engagement(engagement_id: str) -> dict | None:
    return fetch_one(
        f"select {ENGAGEMENT_COLUMNS} from {ENGAGEMENT_FROM} where e.id::text = %s", (engagement_id,)
    )


# Both sides get the other's phone number only once the provider has taken the job
CONTACT_SHARED = ("accepted", "in_progress", "completed")


def client_view(engagement: dict) -> dict:
    """What the hiring client sees: staff notes stay internal."""
    from services import payment_service

    view = {k: v for k, v in engagement.items() if k not in STAFF_ONLY}
    view["contact_shared"] = engagement["status"] in CONTACT_SHARED
    if not view["contact_shared"]:
        view["provider_phone"] = None
        view["provider_telegram"] = None
    # What the client will pay: the price, plus VAT when the provider is VAT-registered
    if engagement.get("agreed_price"):
        b = payment_service.breakdown(engagement["agreed_price"], bool(engagement.get("provider_vat_registered")))
        view["amount_due"] = float(b["total"])
        view["vat_due"] = float(b["provider_vat"])
    return view


def provider_view(engagement: dict) -> dict:
    """What the provider sees: the client's number appears once they accept."""
    from services import reputation

    view = {k: v for k, v in engagement.items() if k not in STAFF_ONLY}
    view["contact_shared"] = engagement["status"] in CONTACT_SHARED
    if not view["contact_shared"]:
        view["client_phone"] = None
        view["client_telegram"] = None
    # What the provider needs to decide on this client; shown only to the provider of this job
    view["client_record"] = reputation.client_record(engagement.get("client_user_id"))
    return view


def _provider_user(provider_id: str | None) -> str | None:
    if not provider_id:
        return None
    row = fetch_one("select user_id::text from providers where id = %s", (provider_id,))
    return row["user_id"] if row else None


def _tell(eng: dict, to: str, title: str, body: str | None = None) -> None:
    """Hire updates go to the bell of the other side. to: 'client' | 'provider'."""
    from services import notifications

    if to == "client":
        user, link = eng.get("client_user_id"), "/account/requests"
    else:
        user, link = _provider_user(eng.get("provider_id")), "/me/provider?tab=jobs"
    if user:
        try:
            notifications.notify([user], kind=f"hire_{to}", title=title[:140], body=body, link=link)
        except Exception:  # a failed notification never blocks the hire itself
            log.exception("Hire notification failed")


# A client can't flood providers' bells or the staff queue with requests
MAX_WAITING_REQUESTS = 10   # open or requested at once
MAX_REQUESTS_PER_HOUR = 10


def _hire_limit(user_id: str) -> None:
    row = fetch_one(
        "select count(*) filter (where status in ('open', 'requested')) as waiting, "
        "count(*) filter (where created_at > now() - interval '1 hour') as last_hour "
        "from engagements where client_user_id = %s",
        (user_id,),
    )
    if row["waiting"] >= MAX_WAITING_REQUESTS:
        raise MarketplaceError(f"You have {row['waiting']} requests waiting for an answer. Cancel some, or wait for "
                               "providers to reply, before sending more.", 429)
    if row["last_hour"] >= provider_service.MAX_REQUESTS_PER_HOUR:
        raise MarketplaceError("You sent many requests in the last hour. Please try again later.", 429)


def create_hire(data: dict, *, user_id: str) -> dict:
    _hire_limit(user_id)
    service = None
    if data.get("service_id"):
        service = catalog_service.get_service(data["service_id"])
        if not service:
            raise MarketplaceError("Unknown service")
    provider_id = data.get("provider_id")
    if provider_id:
        provider = fetch_one(
            f"select {PRIVATE_COLUMNS} from providers p where (p.id::text = %s or p.slug = %s) "
            f"and p.status = 'approved'", (provider_id, provider_id),
        )
        if not provider:
            raise MarketplaceError("This provider is not available")
        if not fetch_one(f"select 1 from providers p where p.id = %s and {LIVE}", (provider["id"],)):
            # Vetting, agreement or profile no longer complete: the client never learns which
            raise MarketplaceError("This provider can't take new requests right now. Please choose another "
                                   "verified provider.", 409)
        if not provider["accepting_work"]:
            raise MarketplaceError("This provider isn't taking new work right now", 409)
        if provider["user_id"] == user_id:
            raise MarketplaceError("You can't hire yourself", 409)
        provider_id = provider["id"]
    elif not service:
        raise MarketplaceError("Choose a provider, or a service so staff can find one for you")
    title = (data.get("title") or (service["name"] if service else "")).strip()
    if not title:
        raise MarketplaceError("Describe what you need")
    row = fetch_one(
        """
        insert into engagements (client_user_id, client_name, client_phone, client_telegram, provider_id, title,
          service_id, service_name, specialty, sub_city, details, budget, status)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning id::text
        """,
        (user_id, data["client_name"], data["client_phone"], data.get("client_telegram"), provider_id, title[:200],
         service["id"] if service else None, service["name"] if service else None,
         data.get("specialty"), data.get("sub_city"), data.get("details"), data.get("budget"),
         "requested" if provider_id else "open"),
    )
    _event(None, row["id"], "created", who="client", to_status="requested" if provider_id else "open",
           provider_id=provider_id)
    if data.get("client_telegram"):  # remembered for the next hire
        execute("update users set telegram_username = coalesce(telegram_username, %s) where id = %s",
                (data["client_telegram"], user_id))
    eng = provider_service.get_engagement(row["id"])
    if provider_id:
        first = (eng["client_name"] or "A client").split()[0]
        where = f" in {eng['sub_city'].replace('_', ' ').title()}" if eng.get("sub_city") else ""
        _tell(eng, "provider", f"New request: {eng['title']}",
              f"{first}{where} wants to hire you. Accept to see their phone number.")
    return eng


AUTO_CONFIRM_DAYS = 7


def auto_confirm_due() -> int:
    """Without online payment, delivered jobs the client neither confirmed nor disputed close after a week.
    With online payment a job closes only when it is paid."""
    if _payments_on():
        return 0
    rows = fetch_all(
        f"""
        update engagements set client_confirmed_at = now(), auto_confirmed = true, updated_at = now()
        where status = 'completed' and client_confirmed_at is null and not coalesce(disputed, false)
          and completed_at < now() - interval '{AUTO_CONFIRM_DAYS} days'
        returning id::text
        """
    )
    for r in rows:
        _event(None, r["id"], "auto_confirmed", who="system", from_status="completed", to_status="completed",
               note=f"Closed after {AUTO_CONFIRM_DAYS} days with no problem reported")
        eng = provider_service.get_engagement(r["id"])
        if eng.get("provider_id"):
            recompute(eng["provider_id"])
        _tell(eng, "client", f"{eng['title']} was closed", "No problem was reported within a week. You can still leave a review.")
        _tell(eng, "provider", f"{eng['title']} is closed", "It now counts toward your Job Success.")
    return len(rows)


# Client "My hires" tabs: closed, declined and cancelled hires are history
CLIENT_HISTORY = ("(e.status in ('declined', 'cancelled') "
                  "or (e.status = 'completed' and e.client_confirmed_at is not null))")
# Provider "Jobs" tabs
JOB_GROUPS = {
    "new": ("open", "requested"),
    "in_progress": ("accepted", "in_progress"),
    "completed": ("completed",),
    "declined": ("declined", "cancelled"),
}
# What waits on each side (header badges), counted in the database, never from a capped list
CLIENT_MUST_ACT = (
    "(e.status = 'completed' and e.client_confirmed_at is null and e.payment_status <> 'paid') "
    "or (e.status = 'completed' and e.client_confirmed_at > now() - interval '30 days' and r.id is null)"
)
PROVIDER_MUST_ACT = "e.status in ('requested', 'accepted', 'in_progress')"


def job_group_counts(provider_id: str) -> dict:
    rows = fetch_all("select status, count(*) as c from engagements where provider_id = %s group by status", (provider_id,))
    by = {r["status"]: r["c"] for r in rows}
    return {g: sum(by.get(s, 0) for s in sts) for g, sts in JOB_GROUPS.items()}


def client_scope_counts(user_id: str) -> dict:
    row = fetch_one(
        f"select count(*) filter (where {CLIENT_HISTORY}) as history, count(*) filter (where not {CLIENT_HISTORY}) as active "
        "from engagements e where e.client_user_id = %s",
        (user_id,),
    )
    return {"active": row["active"], "history": row["history"]}


def attention(user_id: str) -> dict:
    hires = fetch_one(
        f"select count(*) as c from engagements e left join reviews r on r.engagement_id = e.id "
        f"where e.client_user_id = %s and ({CLIENT_MUST_ACT})",
        (user_id,),
    )["c"]
    me = get_for_user(user_id)
    jobs = fetch_one(f"select count(*) as c from engagements e where e.provider_id = %s and {PROVIDER_MUST_ACT}",
                     (me["id"],))["c"] if me else 0
    return {"hires": hires, "jobs": jobs}


def follow_up_sql() -> str:
    """Delivered but not paid for a while (platform setting follow_up_hours): staff call both sides."""
    hours = platform_settings.get_int("follow_up_hours")
    return ("e.status = 'completed' and e.client_confirmed_at is null and e.payment_status <> 'paid' "
            f"and coalesce(e.completed_at, e.updated_at) < now() - interval '{hours} hours'")


def list_engagements(
    *, status: str | None = None, client_user_id: str | None = None, provider_id: str | None = None,
    disputed: bool | None = None, q: str | None = None, limit: int = 50, offset: int = 0,
    follow_up: bool = False, statuses: tuple[str, ...] | None = None, where_sql: str | None = None,
    payment_status: str | None = None, refund_needed: bool | None = None,
) -> dict:
    auto_confirm_due()
    where, params = ["true"], {}
    if statuses:
        where.append("e.status = any(%(statuses)s)")
        params["statuses"] = list(statuses)
    if where_sql:
        where.append(where_sql)
    if follow_up:
        where.append(follow_up_sql())
    if status:
        where.append("e.status = %(status)s")
        params["status"] = status
    if client_user_id:
        where.append("e.client_user_id = %(client)s")
        params["client"] = client_user_id
    if provider_id:
        where.append("e.provider_id = %(provider)s")
        params["provider"] = provider_id
    if disputed:
        where.append("e.disputed")
    if payment_status:
        where.append("e.payment_status = %(pay)s")
        params["pay"] = payment_status
    if refund_needed is not None:
        where.append("e.refund_needed = %(refund)s")
        params["refund"] = refund_needed
    if q:
        # Title, client, provider, or a reference: the start of the hire id or a payment's tx_ref
        where.append("(e.client_name ilike %(q)s or e.client_phone ilike %(q)s or e.title ilike %(q)s "
                     "or p.display_name ilike %(q)s or p.registration_no ilike %(q)s or e.id::text like %(ref)s "
                     "or exists (select 1 from payments pq where pq.engagement_id = e.id and pq.tx_ref ilike %(q)s))")
        params["q"] = f"%{q}%"
        params["ref"] = f"{q.lower()}%"
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from {ENGAGEMENT_FROM} where {clause}", params)["c"]
    items = fetch_all(
        f"select {ENGAGEMENT_COLUMNS} from {ENGAGEMENT_FROM} where {clause} "
        f"order by e.created_at desc limit %(limit)s offset %(offset)s",
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": items}


def _event(conn, engagement_id: str, action: str, *, who: str, actor: str | None = None,
           from_status: str | None = None, to_status: str | None = None, note: str | None = None,
           provider_id: str | None = None) -> None:
    """One line in the hire's history (engagement_events). who: client | provider | staff | system."""
    (conn.execute if conn else execute)(
        "insert into engagement_events (engagement_id, action, actor_kind, actor, from_status, to_status, provider_id, note) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s)",
        (engagement_id, action, who, actor, from_status, to_status, provider_id, (note or "").strip()[:2000] or None),
    )


def _payments_on() -> bool:
    from services import payment_service

    return payment_service.enabled()
