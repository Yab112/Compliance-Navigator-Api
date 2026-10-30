"""The auth audit log: every sign-in, failure and account change, for staff and for rate limits."""

from __future__ import annotations

from auth.common import ClientInfo
from services.db import execute, fetch_all, fetch_one


# ---------------------------------------------------------------- audit log


def record_event(event: str, *, user_id: str | None = None, email: str | None = None,
                 client: ClientInfo | None = None, detail: str | None = None) -> None:
    client = client or ClientInfo()
    execute(
        """
        insert into auth_events (user_id, email, event, ip, user_agent, detail)
        values (%s, lower(%s), %s, %s, %s, %s)
        """,
        (user_id, email, event, client.ip, (client.user_agent or "")[:300] or None, detail),
    )


def list_events(user_id: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    where, params = ("where e.user_id = %s", [user_id]) if user_id else ("", [])
    return fetch_all(
        f"""
        select e.id, e.user_id::text, coalesce(u.email, e.email) as email, e.event, e.ip,
               e.user_agent, e.detail, e.created_at
        from auth_events e left join users u on u.id = e.user_id
        {where}
        order by e.created_at desc, e.id desc limit %s offset %s
        """,
        [*params, limit, offset],
    )


def count_events(user_id: str | None = None) -> int:
    """Events for one user, or every event when user_id is None."""
    if user_id:
        return fetch_one("select count(*) as n from auth_events where user_id = %s", (user_id,))["n"]
    return fetch_one("select count(*) as n from auth_events")["n"]
