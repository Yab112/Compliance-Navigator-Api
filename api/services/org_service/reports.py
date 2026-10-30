"""Reports from citizens about organizations' services."""

from __future__ import annotations

from services.db import connection, fetch_all, fetch_one
from .helpers import OrgError, _log, _plain


# ---------------------------------------------------------------- reports from citizens


def org_reports(org_id: str, status: str | None = None) -> list[dict]:
    """'This information is wrong' reports about the organization's services."""
    return _plain(fetch_all(
        """
        select f.id::text, f.target_id as service_id, s.name as service_name, f.message, f.status,
               f.org_response, f.org_verdict, f.org_responded_by, f.org_responded_at, f.created_at,
               f.resolution_note, f.resolved_at
        from feedback_flags f left join org_services s on s.id::text = f.target_id
        where f.org_id = %s and (%s::text is null or f.status = %s)
        order by (f.status = 'open') desc, f.created_at desc limit 200
        """,
        (org_id, status, status),
    ))


def respond_report(org_id: str, flag_id: str, *, verdict: str, response: str, actor: str) -> dict:
    """The organization answers a report about its service. It stays open until staff check the answer."""
    from services import feedback_service

    try:
        feedback_service.org_respond(org_id, flag_id, verdict=verdict, response=response, actor=actor)
    except feedback_service.FeedbackError as exc:
        raise OrgError(str(exc), exc.status_code) from exc
    with connection() as conn:
        _log(conn, "report_answered", org_id=org_id, actor=actor, note=response[:200])
    return next(r for r in org_reports(org_id) if r["id"] == flag_id)


def org_for_service(service_id: str) -> str | None:
    row = fetch_one("select org_id::text from org_services where id::text = %s", (service_id,))
    return row["org_id"] if row else None
