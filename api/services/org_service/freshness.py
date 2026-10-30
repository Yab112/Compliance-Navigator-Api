"""Freshness: organizations confirming their live services are still accurate."""

from __future__ import annotations

from services.db import connection, fetch_all, fetch_one
from services import platform_settings
from .helpers import OrgError, _log


# ---------------------------------------------------------------- freshness


def confirm_services(org_id: str, service_ids: list[str] | None, actor: str) -> int:
    """'Still accurate': restart the 90-day clock for live services (all of them when ids is None)."""
    org = fetch_one("select status from organizations where id = %s", (org_id,))
    if not org:
        raise OrgError("Organization not found", 404)
    if org["status"] == "suspended":
        raise OrgError("A suspended organization can't confirm services. Contact the platform team.", 409)
    rows = fetch_all(
        """
        update org_services set last_confirmed_at = now(), last_confirmed_by = %s
        where org_id = %s and published_snapshot is not null and status <> 'archived'
          and (%s::uuid[] is null or id = any(%s::uuid[]))
        returning id::text
        """,
        (actor, org_id, service_ids, service_ids),
    )
    with connection() as conn:
        for r in rows:
            _log(conn, "service_confirmed", org_id=org_id, service_id=r["id"], actor=actor)
    return len(rows)


def count_services_due_for_confirmation() -> int:
    return fetch_one(
        f"""
        select count(*) as c from org_services s join organizations o on o.id = s.org_id
        where s.published_snapshot is not null and s.status <> 'archived' and o.status = 'verified'
          and (s.last_confirmed_at is null or s.last_confirmed_at < now() - interval '{platform_settings.get_int("org_confirm_every_days")} days')
        """
    )["c"]


def services_due_for_confirmation(limit: int = 200) -> list[dict]:
    return fetch_all(
        f"""
        select s.id::text, s.name, s.last_confirmed_at, o.id::text as org_id, o.name as org_name
        from org_services s join organizations o on o.id = s.org_id
        where s.published_snapshot is not null and s.status <> 'archived' and o.status = 'verified'
          and (s.last_confirmed_at is null or s.last_confirmed_at < now() - interval '{platform_settings.get_int("org_confirm_every_days")} days')
        order by s.last_confirmed_at nulls first
        limit %s
        """,
        (limit,),
    )
