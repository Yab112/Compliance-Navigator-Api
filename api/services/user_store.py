"""Accounts in Postgres (self-hosted auth, see auth/service.py)."""

from __future__ import annotations

from config.config import settings
from services.db import execute, fetch_all, fetch_one

USER_COLUMNS = "id::text, email, fullname, phone, telegram_username, role, is_active, preferred_sub_city, last_login_at, created_at"


def _role_for(email: str, current: str | None = None) -> str:
    if email.lower() in settings.admin_email_set:
        return "admin"
    return current or "user"


def get_user_by_email(email: str) -> dict | None:
    return fetch_one(
        f"select {USER_COLUMNS}, password_hash from users where lower(email) = lower(%s)",
        (email,),
    )


def get_user(user_id: str) -> dict | None:
    return fetch_one(f"select {USER_COLUMNS} from users where id = %s", (user_id,))


def get_user_with_hash(user_id: str) -> dict | None:
    return fetch_one(f"select {USER_COLUMNS}, password_hash from users where id = %s", (user_id,))


def create_user(email: str, fullname: str, password_hash: str | None, phone: str | None = None) -> dict:
    return fetch_one(
        f"""
        insert into users (email, fullname, phone, password_hash, role, password_changed_at)
        values (lower(%s), %s, %s, %s, %s, now())
        returning {USER_COLUMNS}
        """,
        (email, fullname, phone, password_hash, _role_for(email)),
    )


def set_password(user_id: str, password_hash: str) -> None:
    execute(
        "update users set password_hash = %s, password_changed_at = now(), updated_at = now() where id = %s",
        (password_hash, user_id),
    )


def update_profile(user_id: str, fields: dict) -> dict | None:
    """Self-service fields only; keys not present are left unchanged."""
    allowed = {k: v for k, v in fields.items() if k in ("fullname", "phone", "preferred_sub_city", "telegram_username")}
    if not allowed:
        return get_user(user_id)
    assignments = ", ".join(f"{k} = %s" for k in allowed)
    return fetch_one(
        f"update users set {assignments}, updated_at = now() where id = %s returning {USER_COLUMNS}",
        (*allowed.values(), user_id),
    )


def touch_login(user_id: str, email: str) -> None:
    # Promote bootstrap admins listed in ADMIN_EMAILS on their next login
    execute(
        """
        update users set last_login_at = now(),
          role = case when %s then 'admin' else role end
        where id = %s
        """,
        (email.lower() in settings.admin_email_set, user_id),
    )


def list_users(q: str | None = None, role: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    where, params = ["true"], []
    if q:
        where.append("(email ilike %s or fullname ilike %s)")
        params += [f"%{q}%", f"%{q}%"]
    if role:
        where.append("role = %s")
        params.append(role)
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from users where {clause}", params)["c"]
    rows = fetch_all(
        f"select {USER_COLUMNS} from users where {clause} order by created_at desc limit %s offset %s",
        [*params, limit, offset],
    )
    return {"total": total, "items": rows}


def update_user(user_id: str, *, role: str | None = None, is_active: bool | None = None) -> dict | None:
    return fetch_one(
        f"""
        update users set
          role = coalesce(%s, role),
          is_active = coalesce(%s, is_active),
          updated_at = now()
        where id = %s
        returning {USER_COLUMNS}
        """,
        (role, is_active, user_id),
    )
