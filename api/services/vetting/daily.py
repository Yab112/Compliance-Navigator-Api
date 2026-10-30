"""Daily maintenance: expire old documents, pause listings, remind providers."""

from __future__ import annotations

from services import platform_settings
from services.db import connection
from services.vetting.common import _notify_provider, _recompute
from services.vetting.rules import EXPIRY_SQL, KINDS, max_age_days

# ---------------------------------------------------------------- daily maintenance


def run_daily(only: list[str] | None = None) -> dict:
    """Mark out-of-date documents expired, suspend listings left without a required document, and
    remind providers before their clearance gets too old. Runs inside the daily maintenance.
    `only` limits the run to some providers (tests)."""
    params = {"max_age": max_age_days(), "remind": platform_settings.get_int("police_clearance_remind_days"),
              "only": only}
    scope = "and (%(only)s::uuid[] is null or d.provider_id = any(%(only)s::uuid[]))"
    with connection() as conn, conn.transaction():
        expired = conn.execute(
            f"""
            update provider_documents d set status = 'expired'
            where d.status = 'verified' and {EXPIRY_SQL} < current_date {scope}
            returning d.provider_id::text, d.kind
            """,
            params,
        ).fetchall()
        # Approved listings whose required document ran out and has no verified replacement
        suspended = conn.execute(
            """
            update providers p set status = 'suspended', updated_at = now(),
              review_note = 'A required document expired. Upload a new one to be listed again.'
            where p.status = 'approved'
              and (%(only)s::uuid[] is null or p.id = any(%(only)s::uuid[])) and exists (
              select 1 from provider_documents d
              where d.provider_id = p.id and d.status = 'expired'
                and d.kind in ('police_clearance', 'trade_licence')
                and not exists (select 1 from provider_documents v where v.provider_id = p.id
                                and v.kind = d.kind and v.status = 'verified')
            )
            returning p.id::text, p.user_id::text
            """,
            params,
        ).fetchall()
        for s in suspended:
            conn.execute(
                "insert into provider_events (provider_id, action, actor, note) values "
                "(%s, 'vetting_suspended', 'daily maintenance', 'Listing paused: a required document expired')",
                (s["id"],),
            )
        due = conn.execute(
            f"""
            update provider_documents d set reminded_at = now()
            where d.status = 'verified' and d.reminded_at is null
              and {EXPIRY_SQL} between current_date and current_date + %(remind)s::int {scope}
            returning d.provider_id::text, d.kind, ({EXPIRY_SQL}) as valid_until
            """,
            params,
        ).fetchall()
    for s in suspended:
        _notify_provider(s["id"], "Your listing is paused",
                         "A required document expired. Upload a new one and staff will check it.")
    for d in due:
        _notify_provider(d["provider_id"], f"Your {KINDS[d['kind']].label.lower()} is getting old",
                         f"It counts until {d['valid_until']:%d %b %Y}. Upload a new one before then to stay listed.")
    for pid in {e["provider_id"] for e in expired}:
        _recompute(pid)
    # Everyone is checked again every day: dates pass, settings and legal documents change
    from services import provider_service

    provider_service.refresh_readiness_all(only=only)
    return {"documents_expired": len(expired), "listings_suspended": len(suspended), "reminders_sent": len(due)}
