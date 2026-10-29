"""Accounts, sessions and password resets, the whole auth flow, self-hosted in Postgres.

Sessions: each sign-in creates an auth_sessions row holding the sha256 of an opaque
refresh token (sent to the browser as an httpOnly cookie). Access tokens are 15-minute
JWTs carrying the session id, and every request checks that the session is still live,
so sign-out, password changes and admin actions take effect immediately.
"""

from __future__ import annotations

import logging
import smtplib
import uuid
from dataclasses import dataclass
from email.message import EmailMessage

from auth import security
from config.config import settings
from schemas.auth_user import AuthUser
from services import user_store
from services.db import connection, execute, fetch_all, fetch_one

log = logging.getLogger(__name__)

MAX_FAILED_PER_EMAIL = 5
MAX_FAILED_PER_IP = 25
LOCKOUT_MINUTES = 15
MAX_REGISTRATIONS_PER_IP_HOUR = 10
# A second refresh with a just-rotated token (two tabs at once) is not treated as theft
ROTATION_GRACE_SECONDS = 30
RESET_TTL_MINUTES = 60


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ClientInfo:
    ip: str | None = None
    user_agent: str | None = None


@dataclass
class SessionTokens:
    user: dict
    access_token: str
    expires_in: int
    refresh_token: str | None  # None when the browser already holds the current cookie


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


def list_events(user_id: str | None = None, limit: int = 100) -> list[dict]:
    where, params = ("where e.user_id = %s", [user_id]) if user_id else ("", [])
    return fetch_all(
        f"""
        select e.id, e.user_id::text, coalesce(u.email, e.email) as email, e.event, e.ip,
               e.user_agent, e.detail, e.created_at
        from auth_events e left join users u on u.id = e.user_id
        {where}
        order by e.created_at desc limit %s
        """,
        [*params, limit],
    )


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


def list_sessions(user_id: str) -> list[dict]:
    return fetch_all(
        """
        select id::text, user_agent, ip, created_at, last_used_at, expires_at
        from auth_sessions
        where user_id = %s and revoked_at is null and expires_at > now()
        order by last_used_at desc
        """,
        (user_id,),
    )


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


# ---------------------------------------------------------------- register / sign in


def register(email: str, password: str, fullname: str, phone: str | None, client: ClientInfo) -> SessionTokens:
    problem = security.password_problem(password)
    if problem:
        raise AuthError(problem, 422)
    recent = fetch_one(
        """
        select count(*) as c from auth_events
        where event = 'register' and ip = %s and created_at > now() - interval '1 hour'
        """,
        (client.ip,),
    )
    if client.ip and recent["c"] >= MAX_REGISTRATIONS_PER_IP_HOUR:
        raise AuthError("Too many accounts created from this network. Try again later.", 429)
    if user_store.get_user_by_email(email):
        raise AuthError("An account with this email already exists", 409)
    user = user_store.create_user(email, fullname.strip(), security.hash_password(password), phone=phone)
    record_event("register", user_id=user["id"], email=email, client=client)
    tokens = _create_session(user, client)
    user_store.touch_login(user["id"], user["email"])
    return tokens


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
    user = user_store.get_user(user["id"])  # role may have been promoted via ADMIN_EMAILS
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
        select u.id::text, u.email, u.fullname, u.role
        from users u join auth_sessions s on s.user_id = u.id
        where u.id = %s and s.id = %s and u.is_active
          and s.revoked_at is null and s.expires_at > now()
        """,
        (claims["sub"], claims["sid"]),
    )
    if not row:
        return None
    return AuthUser(id=row["id"], email=row["email"], fullname=row["fullname"], role=row["role"]), claims["sid"]


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


def create_reset_link(user: dict, created_by: str) -> str:
    token = security.new_opaque_token()
    # Only the newest link works
    execute("update password_reset_tokens set used_at = now() where user_id = %s and used_at is null", (user["id"],))
    execute(
        """
        insert into password_reset_tokens (user_id, token_hash, created_by, expires_at)
        values (%s, %s, %s, now() + make_interval(mins => %s))
        """,
        (user["id"], security.token_hash(token), created_by, RESET_TTL_MINUTES),
    )
    return f"{settings.web_base_url.rstrip('/')}/reset-password?token={token}"


def request_password_reset(email: str, client: ClientInfo) -> None:
    """Always succeeds from the caller's point of view, so it can't reveal who has an account."""
    user = user_store.get_user_by_email(email)
    record_event("password_reset_requested", user_id=user["id"] if user else None, email=email, client=client)
    if not user or not user["is_active"]:
        return
    link = create_reset_link(user, created_by="self")
    if settings.smtp_host:
        _send_reset_email(user, link)
    else:
        log.warning("Password reset link for %s (no SMTP configured): %s", user["email"], link)


def _send_reset_email(user: dict, link: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Reset your Compliance Navigator password"
    msg["From"] = settings.smtp_from
    msg["To"] = user["email"]
    msg.set_content(
        f"Hello {user['fullname'] or ''},\n\n"
        f"Use this link within {RESET_TTL_MINUTES} minutes to choose a new password:\n{link}\n\n"
        "If you didn't ask for this, you can ignore this email.\n"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(msg)
    except Exception:
        log.exception("Could not send password reset email to %s", user["email"])


def reset_password(token: str, new: str, client: ClientInfo) -> None:
    problem = security.password_problem(new)
    if problem:
        raise AuthError(problem, 422)
    row = fetch_one(
        """
        update password_reset_tokens set used_at = now()
        where token_hash = %s and used_at is null and expires_at > now()
        returning user_id::text
        """,
        (security.token_hash(token),),
    )
    if not row:
        raise AuthError("This reset link is invalid or has expired. Request a new one.", 400)
    user_store.set_password(row["user_id"], security.hash_password(new))
    revoke_all_sessions(row["user_id"], "password_reset")
    record_event("password_reset", user_id=row["user_id"], client=client)
