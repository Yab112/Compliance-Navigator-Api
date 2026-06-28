"""Verify Supabase Auth JWTs and manage users via Admin API."""

from __future__ import annotations

from config.config import settings
from schemas.auth_user import AuthUser
from services.supabase_client import get_supabase, is_supabase_configured
from services.supabase_store import upsert_profile


def is_auth_configured() -> bool:
    return is_supabase_configured()


def verify_access_token(token: str) -> AuthUser | None:
    if not is_auth_configured():
        return None

    sb = get_supabase()
    try:
        res = sb.auth.get_user(token)
        if not res or not res.user:
            return None
        u = res.user
        meta = u.user_metadata or {}
        fullname = meta.get("fullname") or meta.get("full_name") or ""
        user = AuthUser(
            id=str(u.id),
            email=u.email or "",
            fullname=fullname,
        )
        upsert_profile(user.email, user.fullname, user.id)
        return user
    except Exception:
        return None


def register_user(email: str, password: str, fullname: str) -> dict:
    if not is_auth_configured():
        raise RuntimeError("Supabase is not configured")

    sb = get_supabase()
    res = sb.auth.admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"fullname": fullname},
        }
    )
    u = res.user
    upsert_profile(email, fullname, str(u.id))
    return {
        "id": str(u.id),
        "email": u.email,
        "fullname": fullname,
    }


def sign_in_with_password(email: str, password: str) -> dict:
    """Server-side login — returns Supabase session tokens."""
    if not is_auth_configured():
        raise RuntimeError("Supabase is not configured")

    sb = get_supabase()
    res = sb.auth.sign_in_with_password({"email": email, "password": password})
    session = res.session
    if not session:
        raise ValueError("No session returned")

    u = res.user
    meta = (u.user_metadata or {}) if u else {}
    fullname = meta.get("fullname", "")
    if u:
        upsert_profile(u.email or email, fullname, str(u.id))

    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "type": "Bearer",
        "expires_in": session.expires_in,
    }
