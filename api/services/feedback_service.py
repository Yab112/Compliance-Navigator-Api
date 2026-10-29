"""'This is wrong' flags from users, reviewed in the admin queue.

An organization can answer a report about its own service, but only staff resolve or dismiss
one. Every step is added to feedback_flag_events, so the history is never overwritten.
"""

from __future__ import annotations

import logging

from services import platform_settings
from services.db import connection, fetch_all, fetch_one

log = logging.getLogger(__name__)

COLUMNS = """
  f.id::text, f.user_id::text, u.email as user_email, f.target_type, f.target_id,
  f.message, f.status, f.resolution_note, f.resolved_by, f.created_at, f.resolved_at,
  f.org_id::text, o.name as org_name, f.org_response, f.org_verdict, f.org_responded_by, f.org_responded_at,
  coalesce((select json_agg(json_build_object('action', e.action, 'actor', e.actor, 'note', e.note,
                                              'created_at', e.created_at) order by e.created_at, e.id)
            from feedback_flag_events e where e.flag_id = f.id), '[]'::json) as events
"""
FROM = "feedback_flags f left join users u on u.id = f.user_id left join organizations o on o.id = f.org_id"
TARGET_TYPES = ("document", "gov_service", "office", "agent", "roadmap_step", "org_service", "other")
# 'org_responded' is a view of open reports the organization has answered; it isn't stored
STATUS_FILTERS = ("open", "org_responded", "resolved", "dismissed", "all")


class FeedbackError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _event(conn, flag_id: str, action: str, actor: str | None, note: str | None = None) -> None:
    conn.execute(
        "insert into feedback_flag_events (flag_id, action, actor, note) values (%s, %s, %s, %s)",
        (flag_id, action, actor, note),
    )


def create_flag(target_type: str, target_id: str | None, message: str, user_id: str | None,
                ip: str | None = None) -> dict:
    # Anonymous reports are limited per address, signed-in ones per account, like support requests
    limit = platform_settings.get_int("feedback_flags_per_ip_hour")
    if user_id:
        recent = fetch_one("select count(*) as c from feedback_flags where user_id = %s "
                           "and created_at > now() - interval '1 hour'", (user_id,))["c"]
    elif ip:
        recent = fetch_one("select count(*) as c from feedback_flags where ip = %s and user_id is null "
                           "and created_at > now() - interval '1 hour'", (ip,))["c"]
    else:
        recent = 0
    if recent >= limit:
        raise FeedbackError("Too many reports from this connection. Please try again later.", 429)
    # Reports about an organization's own service also land in that organization's inbox
    org_id = None
    if target_type == "org_service" and target_id:
        org = fetch_one("select org_id::text from org_services where id::text = %s", (target_id,))
        org_id = org["org_id"] if org else None
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "insert into feedback_flags (user_id, target_type, target_id, message, org_id, ip) "
            "values (%s, %s, %s, %s, %s, %s) returning id::text",
            (user_id, target_type, target_id, message, org_id, ip),
        ).fetchone()
        _event(conn, row["id"], "created", None)
    return get_flag(row["id"])


def get_flag(flag_id: str) -> dict | None:
    return fetch_one(f"select {COLUMNS} from {FROM} where f.id::text = %s", (flag_id,))


def _where(status: str | None, target_type: str | None, org_id: str | None, q: str | None) -> tuple[str, dict]:
    where = ["true"]
    params: dict = {}
    if status == "org_responded":
        where.append("f.status = 'open' and f.org_response is not null")
    elif status and status != "all":
        where.append("f.status = %(status)s")
        params["status"] = status
    if target_type:
        where.append("f.target_type = %(target_type)s")
        params["target_type"] = target_type
    if org_id:
        where.append("f.org_id::text = %(org_id)s")
        params["org_id"] = org_id
    if q and q.strip():
        where.append("(f.message ilike %(q)s or f.target_id ilike %(q)s or f.org_response ilike %(q)s "
                     "or exists (select 1 from organizations o2 where o2.id = f.org_id and o2.name ilike %(q)s))")
        params["q"] = f"%{q.strip()}%"
    return " and ".join(where), params


def list_flags(status: str | None = None, limit: int = 50, offset: int = 0, *, target_type: str | None = None,
               org_id: str | None = None, q: str | None = None) -> list[dict]:
    clause, params = _where(status, target_type, org_id, q)
    return fetch_all(
        f"select {COLUMNS} from {FROM} where {clause} "
        "order by f.created_at desc limit %(limit)s offset %(offset)s",
        {**params, "limit": limit, "offset": offset},
    )


def count_flags(status: str | None = None, *, target_type: str | None = None, org_id: str | None = None,
                q: str | None = None) -> int:
    clause, params = _where(status, target_type, org_id, q)
    return fetch_one(f"select count(*) as c from feedback_flags f where {clause}", params)["c"]


def resolve_flag(flag_id: str, status: str, note: str | None, actor: str) -> dict | None:
    """Staff decision. Resolve or dismiss an open report, or reopen a closed one."""
    note = (note or "").strip() or None
    with connection() as conn, conn.transaction():
        flag = conn.execute(
            "select id::text, status, user_id::text, target_type from feedback_flags where id::text = %s for update",
            (flag_id,),
        ).fetchone()
        if not flag:
            return None
        if status == "open":
            if flag["status"] == "open":
                raise FeedbackError("This report is already open", 409)
            # The earlier decision stays in the history; the report itself starts fresh
            conn.execute(
                "update feedback_flags set status = 'open', resolution_note = null, resolved_by = null, "
                "resolved_at = null where id = %s",
                (flag_id,),
            )
            _event(conn, flag_id, "reopened", actor, note)
        else:
            if flag["status"] != "open":
                raise FeedbackError(f"This report is already {flag['status']}", 409)
            conn.execute(
                "update feedback_flags set status = %s, resolution_note = %s, resolved_by = %s, resolved_at = now() "
                "where id = %s",
                (status, note, actor, flag_id),
            )
            _event(conn, flag_id, status, actor, note)
    if status == "resolved" and flag["user_id"]:
        try:
            from services import notifications

            notifications.notify(
                [flag["user_id"]], kind="report_resolved",
                title="Thank you: the information you reported was checked and corrected",
                body=note,
            )
        except Exception:
            log.exception("Could not tell the reporter that flag %s was resolved", flag_id)
    return get_flag(flag_id)


def org_respond(org_id: str, flag_id: str, *, verdict: str, response: str, actor: str) -> None:
    """An organization answers a report about its service. The report stays open until staff check it."""
    with connection() as conn, conn.transaction():
        flag = conn.execute(
            "select status from feedback_flags where id::text = %s and org_id = %s for update", (flag_id, org_id)
        ).fetchone()
        if not flag:
            raise FeedbackError("Report not found", 404)
        if flag["status"] != "open":
            raise FeedbackError(f"Staff already marked this report {flag['status']}", 409)
        conn.execute(
            "update feedback_flags set org_response = %s, org_verdict = %s, org_responded_by = %s, "
            "org_responded_at = now() where id::text = %s",
            (response, verdict, actor, flag_id),
        )
        _event(conn, flag_id, "org_responded", actor,
               ("Fixed: " if verdict == "fixed" else "Information is correct: ") + response)
