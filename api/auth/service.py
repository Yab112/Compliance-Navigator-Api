"""Accounts, sessions and password resets, the whole auth flow, self-hosted in Postgres.

Sessions: each sign-in creates an auth_sessions row holding the sha256 of an opaque
refresh token (sent to the browser as an httpOnly cookie). Access tokens are 15-minute
JWTs carrying the session id, and every request checks that the session is still live,
so sign-out, password changes and admin actions take effect immediately.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Session, audit and email functions live in their own modules; callers and tests use them as auth.service.<name>
from auth import security
from auth.audit import count_events, list_events, record_event
from auth.common import AuthError, ClientInfo, Email, SessionTokens
from auth.emails import (
    RESET_TTL_MINUTES,
    VERIFY_TTL_HOURS,
    _existing_account_email,
    _verification_email,
    create_reset_link,
    create_verification_link,
    request_password_reset,
    resend_verification,
    reset_password,
    send_email,
    verify_email,
)
from auth.sessions import (
    ACTIVE_SESSION,
    _create_session,
    count_active_sessions,
    count_sessions,
    list_sessions,
    public_user,
    revoke_all_sessions,
    revoke_session,
)
from config.config import settings
from schemas.auth_user import AuthUser
from services import user_store
from services.db import connection, execute, fetch_one

__all__ = [
    "ACTIVE_SESSION", "LOCKOUT_MINUTES", "MAX_FAILED_PER_EMAIL", "MAX_FAILED_PER_IP", "MAX_REGISTER_EMAILS_PER_HOUR",
    "MAX_REGISTRATIONS_PER_IP_HOUR", "RESET_TTL_MINUTES", "ROTATION_GRACE_SECONDS", "VERIFY_TTL_HOURS",
    "AuthError", "ClientInfo", "Email", "SessionTokens",
    "change_password", "count_active_sessions", "count_events", "count_sessions", "create_reset_link",
    "create_verification_link", "list_events", "list_sessions", "login", "logout", "public_user", "record_event",
    "refresh", "register", "request_password_reset", "resend_verification", "reset_password", "resolve_access_token",
    "revoke_all_sessions", "revoke_session", "send_email", "settings", "verify_email",
]

MAX_FAILED_PER_EMAIL = 5
MAX_FAILED_PER_IP = 25
LOCKOUT_MINUTES = 15
MAX_REGISTRATIONS_PER_IP_HOUR = 10
# A second refresh with a just-rotated token (two tabs at once) is not treated as theft
ROTATION_GRACE_SECONDS = 30
# Sign-up attempts for one address: the owner gets at most this many "someone used your email" notes an hour
MAX_REGISTER_EMAILS_PER_HOUR = 3


def _recent_failures(column: str, value: str | None) -> int:
    if not value:
        return 0
    expr = "lower(email) = lower(%s)" if column == "email" else "ip = %s"
    row = fetch_one(
        f"""
        select count(*) as c from auth_events
        where event = 'login_failed' and {expr}
          and created_at > now() - make_interval(mins => %s)
          -- a successful sign-in resets the counter
          and created_at > coalesce((
            select max(created_at) from auth_events
            where event = 'login_success' and {expr}
          ), '-infinity')
        """,
        (value, LOCKOUT_MINUTES, value),
    )
    return row["c"]


# ---------------------------------------------------------------- register / sign in


def register(email: str, password: str, fullname: str, phone: str | None, client: ClientInfo,
             on_created: Callable[[Any, dict], None] | None = None) -> Email | None:
    """Create an unverified account and return the email to send (in the background).

    The caller answers "Check your email to continue" either way. When the address already has an
    account, nothing is created and its owner is told someone tried to sign up with it, so the
    response never reveals who has an account. `on_created(conn, user)` runs in the same
    transaction as the new account (e.g. saving consents).
    """
    problem = security.password_problem(password)
    if problem:
        raise AuthError(problem, 422)
    recent = fetch_one(
        """
        select count(*) as c from auth_events
        where event in ('register', 'register_existing') and ip = %s and created_at > now() - interval '1 hour'
        """,
        (client.ip,),
    )
    if client.ip and recent["c"] >= MAX_REGISTRATIONS_PER_IP_HOUR:
        raise AuthError("Too many accounts created from this network. Try again later.", 429)
    # Hash before looking the address up, so both answers take about as long
    password_hash = security.hash_password(password)
    existing = user_store.get_user_by_email(email)
    if existing:
        record_event("register_existing", user_id=existing["id"], email=email, client=client)
        from core import ratelimit

        if ratelimit.hit("register_email", existing["id"], (ratelimit.Rule(MAX_REGISTER_EMAILS_PER_HOUR, 3600),)):
            return None
        return _existing_account_email(existing)
    with connection() as conn, conn.transaction():
        user = user_store.create_user(email, fullname.strip(), password_hash, phone=phone, conn=conn)
        if on_created:
            on_created(conn, user)
    record_event("register", user_id=user["id"], email=email, client=client)
    return _verification_email(user, create_verification_link(user))


def login(email: str, password: str, client: ClientInfo) -> SessionTokens:
    if (
        _recent_failures("email", email) >= MAX_FAILED_PER_EMAIL
        or _recent_failures("ip", client.ip) >= MAX_FAILED_PER_IP
    ):
        record_event("login_blocked", email=email, client=client)
        raise AuthError(
            f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes or reset your password.", 429
        )
    user = user_store.get_user_by_email(email)
    if not security.check_password(password, user["password_hash"] if user else None):
        record_event("login_failed", user_id=user["id"] if user else None, email=email, client=client)
        raise AuthError("Incorrect email or password", 401)
    if not user["is_active"]:
        record_event("login_failed", user_id=user["id"], email=email, client=client, detail="deactivated")
        raise AuthError("This account has been deactivated. Contact an administrator.", 403)
    user_store.touch_login(user["id"], user["email"])
    record_event("login_success", user_id=user["id"], email=email, client=client)
    return _create_session(user, client)


def refresh(refresh_token: str | None, client: ClientInfo) -> SessionTokens:
    if not refresh_token:
        raise AuthError("Not signed in", 401)
    reused = None
    with connection() as conn, conn.transaction():
        session = conn.execute(
            """
            select s.id::text, s.user_id::text, s.family_id::text, s.revoked_at, s.revoked_reason,
                   s.replaced_by::text, s.expires_at > now() as live,
                   s.revoked_at > now() - make_interval(secs => %s) as in_grace
            from auth_sessions s where s.refresh_hash = %s
            for update
            """,
            (ROTATION_GRACE_SECONDS, security.token_hash(refresh_token)),
        ).fetchone()
        if not session:
            raise AuthError("Session not found. Please sign in again.", 401)

        if session["revoked_at"] is not None:
            if session["revoked_reason"] == "rotated" and session["in_grace"] and session["replaced_by"]:
                # Concurrent refresh from another tab: the cookie already holds the new token,
                # so hand back an access token for the replacement session only.
                user = user_store.get_user(session["user_id"])
                replacement = conn.execute(
                    "select id::text from auth_sessions where id = %s and revoked_at is null",
                    (session["replaced_by"],),
                ).fetchone()
                if user and user["is_active"] and replacement:
                    access, ttl = security.issue_access_token(user["id"], replacement["id"], user["role"])
                    return SessionTokens(public_user(user), access, ttl, None)
            if session["revoked_reason"] == "rotated":
                reused = session
            else:
                raise AuthError("Your session has ended. Please sign in again.", 401)

        if reused is None:
            if not session["live"]:
                raise AuthError("Your session has expired. Please sign in again.", 401)
            user = user_store.get_user(session["user_id"])
            if not user or not user["is_active"]:
                raise AuthError("This account has been deactivated.", 401)

            new_refresh = security.new_opaque_token()
            new_row = conn.execute(
                """
                insert into auth_sessions (user_id, family_id, refresh_hash, user_agent, ip, expires_at)
                values (%s, %s, %s, %s, %s, now() + make_interval(days => %s))
                returning id::text
                """,
                (user["id"], session["family_id"], security.token_hash(new_refresh),
                 (client.user_agent or "")[:300] or None, client.ip, settings.refresh_token_ttl_days),
            ).fetchone()
            conn.execute(
                """
                update auth_sessions set revoked_at = now(), revoked_reason = 'rotated', replaced_by = %s
                where id = %s
                """,
                (new_row["id"], session["id"]),
            )
    if reused:
        # An old refresh token came back after rotation: assume it was stolen and end
        # every session descended from the same sign-in. (Outside the transaction above,
        # which only reads in this case.)
        execute(
            """
            update auth_sessions set revoked_at = now(), revoked_reason = 'reuse_detected'
            where family_id = %s and revoked_at is null
            """,
            (reused["family_id"],),
        )
        record_event("refresh_reuse", user_id=reused["user_id"], client=client)
        raise AuthError("Your session has ended. Please sign in again.", 401)
    access, ttl = security.issue_access_token(user["id"], new_row["id"], user["role"])
    return SessionTokens(public_user(user), access, ttl, new_refresh)


def logout(refresh_token: str | None, session_id: str | None, client: ClientInfo) -> None:
    row = None
    if refresh_token:
        row = fetch_one(
            """
            update auth_sessions set revoked_at = now(), revoked_reason = 'logout'
            where refresh_hash = %s and revoked_at is null
            returning user_id::text
            """,
            (security.token_hash(refresh_token),),
        )
    if not row and session_id:
        row = fetch_one(
            """
            update auth_sessions set revoked_at = now(), revoked_reason = 'logout'
            where id = %s and revoked_at is null returning user_id::text
            """,
            (session_id,),
        )
    if row:
        record_event("logout", user_id=row["user_id"], client=client)


def resolve_access_token(token: str) -> tuple[AuthUser, str] | None:
    """The user and session id behind an access token, if both are still valid."""
    claims = security.decode_access_token(token)
    if not claims:
        return None
    row = fetch_one(
        """
        select u.id::text, u.email, u.fullname, u.role, u.email_verified_at is not null as email_verified
        from users u join auth_sessions s on s.user_id = u.id
        where u.id = %s and s.id = %s and u.is_active
          and s.revoked_at is null and s.expires_at > now()
        """,
        (claims["sub"], claims["sid"]),
    )
    if not row:
        return None
    return AuthUser(id=row["id"], email=row["email"], fullname=row["fullname"], role=row["role"],
                    email_verified=row["email_verified"]), claims["sid"]


# ---------------------------------------------------------------- passwords


def change_password(user_id: str, current: str, new: str, session_id: str, client: ClientInfo) -> int:
    user = user_store.get_user_with_hash(user_id)
    if not user or not security.check_password(current, user["password_hash"]):
        record_event("password_change_failed", user_id=user_id, client=client)
        raise AuthError("Current password is incorrect", 400)
    problem = security.password_problem(new)
    if problem:
        raise AuthError(problem, 422)
    if current == new:
        raise AuthError("The new password must be different", 422)
    user_store.set_password(user_id, security.hash_password(new))
    signed_out = revoke_all_sessions(user_id, "password_changed", keep_session_id=session_id)
    record_event("password_changed", user_id=user_id, client=client)
    return signed_out
