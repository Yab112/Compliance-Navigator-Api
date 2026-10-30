"""Sessions: creating, listing and revoking a person's signed-in sessions."""

from __future__ import annotations

import uuid

from auth import security
from auth.common import ClientInfo, SessionTokens
from config.config import settings
from services.db import fetch_all, fetch_one


# ---------------------------------------------------------------- sessions


def _create_session(user: dict, client: ClientInfo, family_id: str | None = None) -> SessionTokens:
    refresh = security.new_opaque_token()
    row = fetch_one(
        """
        insert into auth_sessions (user_id, family_id, refresh_hash, user_agent, ip, expires_at)
        values (%s, %s, %s, %s, %s, now() + make_interval(days => %s))
        returning id::text
        """,
        (user["id"], family_id or str(uuid.uuid4()), security.token_hash(refresh),
         (client.user_agent or "")[:300] or None, client.ip, settings.refresh_token_ttl_days),
    )
    access, ttl = security.issue_access_token(user["id"], row["id"], user["role"])
    return SessionTokens(user=public_user(user), access_token=access, expires_in=ttl, refresh_token=refresh)


def public_user(user: dict) -> dict:
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "fullname": user["fullname"],
        "phone": user.get("phone"),
        "telegramUsername": user.get("telegram_username"),
        "role": user["role"],
        "preferredSubCity": user.get("preferred_sub_city"),
        "emailVerified": user.get("email_verified_at") is not None,
    }


def revoke_session(session_id: str, reason: str, user_id: str | None = None) -> bool:
    row = fetch_one(
        """
        update auth_sessions set revoked_at = now(), revoked_reason = %s
        where id = %s and revoked_at is null and (%s::uuid is null or user_id = %s::uuid)
        returning id
        """,
        (reason, session_id, user_id, user_id),
    )
    return row is not None


def revoke_all_sessions(user_id: str, reason: str, keep_session_id: str | None = None) -> int:
    rows = fetch_all(
        """
        update auth_sessions set revoked_at = now(), revoked_reason = %s
        where user_id = %s and revoked_at is null and (%s::uuid is null or id <> %s::uuid)
        returning id
        """,
        (reason, user_id, keep_session_id, keep_session_id),
    )
    return len(rows)


ACTIVE_SESSION = "user_id = %s and revoked_at is null and expires_at > now()"


def list_sessions(user_id: str, limit: int | None = None, offset: int = 0) -> list[dict]:
    return fetch_all(
        f"""
        select id::text, user_agent, ip, created_at, last_used_at, expires_at
        from auth_sessions
        where {ACTIVE_SESSION}
        order by last_used_at desc, id limit %s offset %s
        """,
        (user_id, limit, offset),
    )


def count_sessions(user_id: str) -> int:
    return fetch_one(f"select count(*) as n from auth_sessions where {ACTIVE_SESSION}", (user_id,))["n"]


def count_active_sessions(user_ids: list[str]) -> dict[str, int]:
    if not user_ids:
        return {}
    rows = fetch_all(
        """
        select user_id::text, count(*) as c from auth_sessions
        where user_id = any(%s::uuid[]) and revoked_at is null and expires_at > now()
        group by user_id
        """,
        (user_ids,),
    )
    return {r["user_id"]: r["c"] for r in rows}
