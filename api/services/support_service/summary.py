"""Desk totals for the staff dashboard."""

from __future__ import annotations

from services.db import execute, fetch_all, fetch_one
from services import platform_settings
from .common import OVERDUE_SQL, QUEUES


# ---------------------------------------------------------------- summary


def summary(staff_id: str | None) -> dict:
    from services import provider_service

    totals = fetch_one(
        f"""
        select count(*) filter (where t.status = 'new') as new,
               count(*) filter (where t.status = 'open') as open,
               count(*) filter (where t.status = 'waiting_customer') as waiting_customer,
               count(*) filter (where {OVERDUE_SQL}) as overdue,
               count(*) filter (where t.status in ('new', 'open', 'waiting_customer') and t.assignee_id is null) as unassigned,
               count(*) filter (where t.status in ('new', 'open', 'waiting_customer') and t.assignee_id = %s) as mine,
               count(*) filter (where t.status in ('resolved', 'closed') and t.resolved_at > now() - interval '7 days') as resolved_7d,
               round(avg(extract(epoch from t.first_response_at - t.created_at) / 60)
                     filter (where t.first_response_at > now() - interval '30 days'))::int as avg_first_response_minutes
        from support_tickets t
        """,
        (staff_id,),
    )
    by_queue = {
        r["queue"]: r for r in fetch_all(
            f"""
            select t.queue, count(*) filter (where t.status in ('new', 'open', 'waiting_customer')) as open,
                   count(*) filter (where t.status in ('new', 'open', 'waiting_customer') and t.assignee_id is null) as unassigned,
                   count(*) filter (where {OVERDUE_SQL}) as overdue
            from support_tickets t group by t.queue
            """
        )
    }
    queues = [{"key": k, "label": v[0], **{f: (by_queue.get(k) or {}).get(f, 0) for f in ("open", "unassigned", "overdue")}}
              for k, v in QUEUES.items()]

    def count(sql: str) -> int:
        try:
            return fetch_one(sql)["c"]
        except Exception:
            return 0

    related = {
        "hires_unmatched": count("select count(*) as c from engagements where provider_id is null and status = 'open'"),
        "deals_to_follow_up": count(f"select count(*) as c from engagements e where {provider_service.follow_up_sql()}"),
        "wrong_info_reports": count("select count(*) as c from feedback_flags where status = 'open'"),
        "providers_pending": count("select count(*) as c from providers where status = 'pending'"),
        "org_submissions_pending": count(
            "select (select count(*) from organizations where status = 'pending') "
            "+ (select count(*) from org_service_revisions where status = 'pending') as c"
        ),
    }
    return {"totals": totals, "queues": queues, "related": related,
            "follow_up_hours": platform_settings.get_int("follow_up_hours")}


def purge_for_tests(ip: str) -> int:
    return execute("delete from support_tickets where ip = %s", (ip,))
