"""Account emails: sending them, password reset links and email verification."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from auth import security
from auth.audit import record_event
from auth.common import AuthError, ClientInfo, Email
from auth.sessions import public_user, revoke_all_sessions
from config.config import settings
from services import user_store
from services.db import connection, execute, fetch_one

log = logging.getLogger(__name__)


RESET_TTL_MINUTES = 60
VERIFY_TTL_HOURS = 48


# ---------------------------------------------------------------- password resets


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


def request_password_reset(email: str, client: ClientInfo) -> Email | None:
    """The email to send, if any. The caller always answers the same, so it can't reveal who has an account."""
    user = user_store.get_user_by_email(email)
    record_event("password_reset_requested", user_id=user["id"] if user else None, email=email, client=client)
    if not user or not user["is_active"]:
        return None
    from core import ratelimit

    # A few links an hour per address; more requests are quietly not sent (each one replaces the last link)
    if ratelimit.hit("forgot_password_email", user["id"]):
        return None
    link = create_reset_link(user, created_by="self")
    return Email(
        to=user["email"],
        subject="Reset your Compliance Navigator password",
        text=(
            f"Hello {user['fullname'] or ''},\n\n"
            f"Use this link within {RESET_TTL_MINUTES} minutes to choose a new password:\n{link}\n\n"
            "If you didn't ask for this, you can ignore this email.\n"
        ),
    )


# ---------------------------------------------------------------- email


def send_email(email: Email) -> None:
    """Send through SMTP. Without SMTP (development only: production refuses to start) the
    message, link included, goes to the API log so a developer can follow it."""
    if not settings.smtp_host:
        if settings.is_production:
            log.error("Email not sent, SMTP is not configured: %s", email.subject)
        else:
            log.warning("DEVELOPMENT ONLY, no SMTP configured. Email to %s: %s\n%s",
                        email.to, email.subject, email.text)
        return
    msg = EmailMessage()
    msg["Subject"] = email.subject
    msg["From"] = settings.smtp_from
    msg["To"] = email.to
    msg.set_content(email.text)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(msg)
    except Exception:
        log.exception("Could not send email: %s", email.subject)


def _existing_account_email(user: dict) -> Email:
    base = settings.web_base_url.rstrip("/")
    return Email(
        to=user["email"],
        subject="Someone tried to create a Compliance Navigator account with your email",
        text=(
            f"Hello {user['fullname'] or ''},\n\n"
            "Someone just tried to create an account with this email address, but you already have one.\n"
            f"If it was you, sign in here: {base}/login\n"
            f"Forgot your password? Choose a new one here: {base}/forgot-password\n\n"
            "If it wasn't you, you can ignore this email. Nothing has changed on your account.\n"
        ),
    )


# ---------------------------------------------------------------- email verification


def create_verification_link(user: dict) -> str:
    token = security.new_opaque_token()
    with connection() as conn, conn.transaction():
        # Only the newest link works
        conn.execute(
            "update email_verification_tokens set used_at = now() where user_id = %s and used_at is null",
            (user["id"],),
        )
        conn.execute(
            """
            insert into email_verification_tokens (user_id, token_hash, email, expires_at)
            values (%s, %s, lower(%s), now() + make_interval(hours => %s))
            """,
            (user["id"], security.token_hash(token), user["email"], VERIFY_TTL_HOURS),
        )
    return f"{settings.web_base_url.rstrip('/')}/verify-email?token={token}"


def _verification_email(user: dict, link: str) -> Email:
    return Email(
        to=user["email"],
        subject="Confirm your email for Compliance Navigator",
        text=(
            f"Hello {user['fullname'] or ''},\n\n"
            f"Please confirm this is your email address. The link works once, within {VERIFY_TTL_HOURS} hours:\n"
            f"{link}\n\n"
            "You can already use your account. Until you confirm, you can't offer services as a provider,\n"
            "create or join an organization, or receive payouts.\n\n"
            "If you didn't create this account, you can ignore this email.\n"
        ),
    )


def resend_verification(user_id: str, client: ClientInfo) -> Email | None:
    """A fresh link for a signed-in person who hasn't confirmed yet; None when already confirmed."""
    user = user_store.get_user(user_id)
    if not user or user.get("email_verified_at") is not None:
        return None
    record_event("email_verification_sent", user_id=user_id, client=client)
    return _verification_email(user, create_verification_link(user))


def verify_email(token: str, client: ClientInfo) -> dict:
    """Use a verification link once. Returns the person's public profile."""
    with connection() as conn, conn.transaction():
        row = conn.execute(
            """
            update email_verification_tokens set used_at = now()
            where token_hash = %s and used_at is null and expires_at > now()
            returning user_id::text, email
            """,
            (security.token_hash(token),),
        ).fetchone()
        user = user_store.mark_email_verified(row["user_id"], row["email"], conn=conn) if row else None
    if not user:
        raise AuthError("This link is invalid or has expired. Sign in and ask for a new one.", 400)
    record_event("email_verified", user_id=user["id"], client=client)
    return public_user(user)


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
