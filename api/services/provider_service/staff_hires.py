"""Staff hire tools: updates, disputes, detail, assigning and CSV export."""

from __future__ import annotations

from services import provider_service
from services.db import connection, fetch_all, fetch_one

from .common import ENGAGEMENT_STATUSES, LIVE, MarketplaceError, _log
from .engagement_actions import _set_status
from .engagements import _event, _provider_user, _tell, list_engagements
from .readiness import not_ready_message
from .trust import recompute

# What staff may do to a hire, from which statuses. Staff never set accepted, in progress or delivered:
# only the provider moves a job forward. Paid (or paying) jobs can't be cancelled or reopened here; the
# money goes back through a refund. Once a provider accepts, the job can't be moved to someone else.
STAFF_HIRE_ACTIONS = {
    "assign": ("open", "requested"),
    "cancel": ("open", "requested", "accepted", "in_progress", "completed"),
    "reopen": ("declined", "cancelled"),
    "note": ENGAGEMENT_STATUSES,
}
NOT_PAID = "and e.payment_status not in ('paid', 'pending')"


def admin_update_engagement(
    engagement_id: str, *, action: str, provider_id: str | None = None, note: str, actor: str,
) -> dict:
    eng = provider_service.get_engagement(engagement_id)
    if not eng:
        raise MarketplaceError("Request not found", 404)
    if action not in STAFF_HIRE_ACTIONS:
        raise MarketplaceError("Unknown action")
    note = (note or "").strip()
    if len(note) < 5:
        raise MarketplaceError("Write a note saying why (at least 5 characters)")
    allowed = STAFF_HIRE_ACTIONS[action]
    if eng["status"] not in allowed:
        reason = {
            "assign": "A provider can only be assigned before anyone accepts the job",
            "cancel": "This job is already closed",
            "reopen": "Only declined or cancelled requests can be reopened",
        }.get(action, "Not possible now")
        raise MarketplaceError(reason, 409)
    if action in ("cancel", "reopen") and eng.get("payment_status") in ("paid", "pending"):
        raise MarketplaceError("This job is paid or being paid. Money goes back through a refund, not by "
                               "cancelling or reopening the job.", 409)
    if action == "cancel" and eng["status"] == "completed" and eng.get("client_confirmed_at"):
        raise MarketplaceError("This job is closed", 409)
    old_provider = eng["provider_id"]
    title = eng["title"]

    if action == "note":
        with connection() as conn, conn.transaction():
            conn.execute("update engagements set admin_note = %s, updated_at = now() where id = %s", (note, engagement_id))
            _event(conn, engagement_id, "staff_note", who="staff", actor=actor, note=note, provider_id=old_provider)
        return provider_service.get_engagement(engagement_id)

    if action == "assign":
        if not provider_id:
            raise MarketplaceError("Choose a provider")
        provider = fetch_one(
            f"select p.id::text, p.user_id::text, p.display_name, p.accepting_work, p.not_ready_reasons, "
            f"({LIVE}) as live from providers p where p.id::text = %s and p.status = 'approved'", (provider_id,))
        if not provider:
            raise MarketplaceError("Only approved providers with a valid licence can be assigned")
        if not provider["live"]:
            raise MarketplaceError(f"{provider['display_name']} can't take work yet: {not_ready_message(provider)}", 409)
        if not provider["accepting_work"]:
            raise MarketplaceError("This provider isn't taking new work right now", 409)
        if provider["id"] == old_provider:
            raise MarketplaceError("This provider already has the request", 409)
        if provider["user_id"] and provider["user_id"] == eng["client_user_id"]:
            raise MarketplaceError("A provider can't be assigned their own request", 409)
        # Never accepted_at: the new provider sees the client's phone only after they accept
        _set_status(engagement_id, "requested", ", provider_id = %s::uuid, admin_note = %s, accepted_at = null",
                    (provider["id"], note), allowed=allowed, who="staff", actor=actor, note=note,
                    action="reassigned" if old_provider else "assigned")
    elif action == "cancel":
        _set_status(engagement_id, "cancelled", ", admin_note = %s", (note,), allowed=allowed, guard=NOT_PAID,
                    who="staff", actor=actor, note=note, action="staff_cancelled")
    elif action == "reopen":
        # Back to the staff queue with no provider, ready to be assigned again
        _set_status(engagement_id, "open", ", provider_id = null, admin_note = %s, accepted_at = null, "
                    "declined_reason = null", (note,), allowed=allowed, guard=NOT_PAID, who="staff", actor=actor,
                    note=note, action="reopened")

    hire = provider_service.get_engagement(engagement_id)
    for pid in {old_provider, hire["provider_id"]} - {None}:
        recompute(pid)
    # Everyone involved hears about it; the staff note itself stays internal
    if action == "assign":
        _tell(hire, "provider", f"New request: {title}",
              "Our team matched you with this client. Accept to see their phone number.")
        if old_provider:
            _tell({**eng, "provider_id": old_provider}, "provider", f"Request moved to another provider: {title}",
                  "Our team reassigned this request. You don't need to do anything.")
        _tell(hire, "client", f"We found a provider for {title}",
              f"{hire['provider_name']} has your request. You will get their phone number once they accept.")
    elif action == "cancel":
        _tell(eng, "client", f"Request cancelled by our team: {title}",
              "If you have questions, contact support from the Help page.")
        _tell(eng, "provider", f"Request cancelled by our team: {title}", "You don't need to do anything more on it.")
    elif action == "reopen":
        _tell(eng, "client", f"We are finding a provider for {title}",
              "Our team reopened your request and will match you with a provider.")
        if old_provider:
            _tell(eng, "provider", f"Request closed for you: {title}", "Our team moved this request back to the queue.")
    return hire


def resolve_dispute(engagement_id: str, decision: str, *, note: str | None, actor: str) -> dict:
    eng = provider_service.get_engagement(engagement_id)
    if not eng or not eng["disputed"]:
        raise MarketplaceError("No complaint on this job", 404)
    if decision not in ("upheld", "dismissed"):
        raise MarketplaceError("Decision must be upheld or dismissed")
    note = (note or "").strip()
    if len(note) < 5:
        raise MarketplaceError("Write the finding (at least 5 characters). The client and provider see it.")
    with connection() as conn, conn.transaction():
        # Decided once: a second click, or a second staff member, gets a 409 instead of flipping it
        row = conn.execute(
            """
            update engagements set dispute_status = %(d)s, dispute_note = %(note)s, dispute_resolved_by = %(actor)s,
              dispute_resolved_at = now(), updated_at = now(),
              -- An upheld complaint on a paid job: the client is owed money back
              refund_needed = refund_needed or (%(d)s = 'upheld' and payment_status = 'paid'),
              refund_flagged_at = case when %(d)s = 'upheld' and payment_status = 'paid' then now() else refund_flagged_at end,
              refund_flagged_by = case when %(d)s = 'upheld' and payment_status = 'paid' then %(actor)s else refund_flagged_by end
            where id = %(id)s and disputed and dispute_status = 'open'
            returning status, refund_needed
            """,
            {"d": decision, "note": note, "actor": actor, "id": engagement_id},
        ).fetchone()
        if not row:
            raise MarketplaceError("This complaint was already decided", 409)
        _event(conn, engagement_id, f"complaint_{decision}", who="staff", actor=actor, from_status=row["status"],
               to_status=row["status"], note=note, provider_id=eng["provider_id"])
        if row["refund_needed"] and decision == "upheld":
            _event(conn, engagement_id, "refund_needed", who="staff", actor=actor,
                   note="Paid job with an upheld complaint", provider_id=eng["provider_id"])
        if eng["provider_id"]:
            _log(conn, eng["provider_id"], f"complaint_{decision}", actor, note)
    if eng["provider_id"]:
        recompute(eng["provider_id"])
    word = "upheld" if decision == "upheld" else "not upheld"
    _tell(eng, "client", f"Your complaint about {eng['title']} was {word}", note[:300])
    _tell(eng, "provider", f"A complaint about {eng['title']} was {word}", note[:300])
    return provider_service.get_engagement(engagement_id)


# ---------------------------------------------------------------- staff hire tools


def admin_hire_detail(engagement_id: str, *, can_see_payments: bool, can_see_support: bool) -> dict | None:
    """One hire for staff: the hire, its full history, payments and the people's support requests."""
    hire = provider_service.get_engagement(engagement_id)
    if not hire:
        return None
    events = fetch_all(
        "select ev.id, ev.action, ev.actor_kind, ev.actor, ev.from_status, ev.to_status, ev.note, ev.created_at, "
        "ev.provider_id::text, p.display_name as provider_name "
        "from engagement_events ev left join providers p on p.id = ev.provider_id "
        "where ev.engagement_id = %s order by ev.id",
        (engagement_id,),
    )
    # Hires from before the history existed: show what the hire itself records
    if not any(e["action"] == "created" for e in events):
        events.insert(0, {"id": None, "action": "created", "actor_kind": "client", "actor": None, "from_status": None,
                          "to_status": None, "note": None, "created_at": hire["created_at"],
                          "provider_id": None, "provider_name": None})
    payments = fetch_all(
        """
        select tx_ref, gateway, amount::float, status, payment_method, gateway_reference, created_at, verified_at,
          commission_amount::float, provider_amount::float
        from payments where engagement_id = %s order by created_at desc
        """,
        (engagement_id,),
    ) if can_see_payments else None
    tickets = None
    if can_see_support:
        people = [u for u in (hire["client_user_id"], _provider_user(hire["provider_id"])) if u]
        tickets = fetch_all(
            """
            select t.id::text, t.ref, t.subject, t.status, t.queue, t.created_at, t.updated_at,
              case when t.user_id = %s then 'client' else 'provider' end as from_side
            from support_tickets t where t.user_id = any(%s::uuid[])
            order by t.created_at desc limit 20
            """,
            (hire["client_user_id"], people),
        ) if people else []
    return {"hire": hire, "events": events, "payments": payments, "tickets": tickets,
            "actions": staff_actions(hire)}


def staff_actions(hire: dict) -> list[str]:
    """What staff may do to this hire now, so the page only offers what the server will accept."""
    paid = hire.get("payment_status") in ("paid", "pending")
    out = []
    for action, allowed in STAFF_HIRE_ACTIONS.items():
        if hire["status"] not in allowed:
            continue
        if action in ("cancel", "reopen") and paid:
            continue
        if action == "cancel" and hire["status"] == "completed" and hire.get("client_confirmed_at"):
            continue
        out.append(action)
    return out


def assign_candidates(engagement_id: str, *, q: str | None = None, area: str | None = None,
                      specialty: str | None = None, limit: int = 20, offset: int = 0) -> dict | None:
    """Providers staff can assign to an open request: listed (approved, licence in date, ready to work) and taking work.
    Ranked by fit (the requested service, then specialty, then area), then trust score."""
    hire = provider_service.get_engagement(engagement_id)
    if not hire:
        return None
    where = [LIVE, "p.accepting_work"]
    params: dict = {"service": hire.get("service_id"), "h_specialty": hire.get("specialty"),
                    "h_area": hire.get("sub_city")}
    if hire.get("provider_id"):
        where.append("p.id <> %(current)s::uuid")
        params["current"] = hire["provider_id"]
    if hire.get("client_user_id"):
        where.append("p.user_id is distinct from %(client)s::uuid")
        params["client"] = hire["client_user_id"]
    if area:
        where.append("(p.sub_city = %(area)s or %(area)s = any(p.service_areas) or 'nationwide' = any(p.service_areas))")
        params["area"] = area
    if specialty:
        where.append("%(specialty)s = any(p.specialties)")
        params["specialty"] = specialty
    if q:
        where.append("(p.display_name ilike %(q)s or p.registration_no ilike %(q)s or p.phone ilike %(q)s)")
        params["q"] = f"%{q}%"
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from providers p where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select p.id::text, p.display_name, p.registration_no, p.provider_type, p.entity_type, p.sub_city,
          p.service_areas, p.specialties, p.trust_score, p.rating_avg::float, p.rating_count, p.completed_count,
          p.license_expires_at,
          coalesce(%(service)s::text = any(p.service_ids), false) as offers_service,
          coalesce(%(h_specialty)s::text = any(p.specialties), false) as same_specialty,
          coalesce(p.sub_city = %(h_area)s::text or %(h_area)s::text = any(p.service_areas), false) as covers_area,
          (select count(*) from engagements e where e.provider_id = p.id
             and e.status = any(array['requested','accepted','in_progress'])) as open_jobs
        from providers p where {clause}
        order by offers_service desc, same_specialty desc, covers_area desc, p.trust_score desc nulls last,
          p.display_name
        limit %(limit)s offset %(offset)s
        """,
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": items}


HIRE_CSV_COLUMNS = (
    ("id", "Hire id"), ("created_at", "Created"), ("title", "Title"), ("status", "Status"),
    ("client_name", "Client"), ("client_phone", "Client phone"), ("provider_name", "Provider"),
    ("provider_registration_no", "Provider registration no."), ("service_name", "Service"),
    ("sub_city", "Sub-city"), ("agreed_price", "Price (ETB)"), ("payment_status", "Payment"),
    ("paid_at", "Paid at"), ("paid_tx_ref", "Payment reference"), ("disputed", "Complaint"),
    ("dispute_status", "Complaint status"), ("refund_needed", "Refund needed"), ("completed_at", "Delivered"),
    ("client_confirmed_at", "Closed"),
)
HIRE_CSV_MAX = 10_000


def _csv_cell(value) -> str:
    """Spreadsheet-safe text: a cell starting with = + - @ (or a tab or return) is a formula to Excel."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_engagements_csv(**filters) -> tuple[str, int]:
    """The hires list as CSV with the same filters, up to HIRE_CSV_MAX rows. Returns (text, row count)."""
    import csv
    import io

    rows = list_engagements(**filters, limit=HIRE_CSV_MAX, offset=0)["items"]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([label for _, label in HIRE_CSV_COLUMNS])
    for r in rows:
        writer.writerow([_csv_cell(r.get(key)) for key, _ in HIRE_CSV_COLUMNS])
    return out.getvalue(), len(rows)
