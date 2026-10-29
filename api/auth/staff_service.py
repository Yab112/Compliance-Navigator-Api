"""
Staff sign-in, sessions, invitations and password links, and the staff audit log.

Separate from auth/service.py on purpose: staff live in staff_users, sessions in staff_sessions,
the refresh cookie has its own name and path, and access tokens come from another issuer with
realm "staff". A public account can never reach an admin route and a staff token never works on
the public site. The mechanics (rotating refresh tokens, reuse detection, lockout) match the public
flow.
"""

from __future__ import annotations

import logging
import smtplib
import uuid
from dataclasses import dataclass
from email.message import EmailMessage

from psycopg.types.json import Jsonb

from auth import security
from auth.service import AuthError, ClientInfo
from config.config import settings
from schemas.staff_user import StaffActor
from services import access
from services.db import connection, execute, fetch_all, fetch_one

log = logging.getLogger(__name__)

MAX_FAILED_PER_EMAIL = 5
MAX_FAILED_PER_IP = 25
LOCKOUT_MINUTES = 15
ROTATION_GRACE_SECONDS = 30
# Staff sessions are short: sign in again every working day
SESSION_TTL_HOURS = 12
INVITE_TTL_HOURS = 48
RESET_TTL_MINUTES = 60

STAFF_COLUMNS = ("s.id::text, s.email, s.fullname, s.status, s.must_change_password, s.last_login_at, "
                 "s.password_changed_at, s.created_by, s.created_at, s.updated_at")


@dataclass
class StaffSession:
    staff: dict
    access_token: str
    expires_in: int
    refresh_token: str | None


# ---------------------------------------------------------------- audit log


def audit(action: str, *, actor: StaffActor | dict | None = None, actor_email: str | None = None,
          target: str | None = None, details: dict | None = None, client: ClientInfo | None = None) -> None:
    """Write one line to the staff audit log. Never raises: auditing must not break the action."""
    client = client or ClientInfo()
    actor_id = getattr(actor, "id", None) or (actor.get("id") if isinstance(actor, dict) else None)
    email = actor_email or getattr(actor, "email", None) or (actor.get("email") if isinstance(actor, dict) else None)
    try:
        execute(
            """
            insert into staff_audit_log (actor_id, actor_email, action, target, details, ip, user_agent)
            values (%s, lower(%s), %s, %s, %s, %s, %s)
            """,
            (actor_id, email, action, target, Jsonb(details or {}), client.ip, (client.user_agent or "")[:300] or None),
        )
    except Exception:
        log.exception("Could not write staff audit entry %s", action)


def list_audit(*, actor: str | None = None, action: str | None = None, target: str | None = None,
               since: str | None = None, until: str | None = None, limit: int = 25, offset: int = 0) -> dict:
    where, params = ["true"], []
    if actor:
        where.append("(lower(a.actor_email) like lower(%s) or a.actor_id::text = %s)")
        params += [f"%{actor}%", actor]
    if action:
        where.append("a.action like %s")
        params.append(f"{action}%")
    if target:
        where.append("a.target ilike %s")
        params.append(f"%{target}%")
    if since:
        where.append("a.created_at >= %s::date")
        params.append(since)
    if until:
        where.append("a.created_at < %s::date + 1")
        params.append(until)
    clause = " and ".join(where)
    items = fetch_all(
        f"""
        select a.id, a.actor_id::text, a.actor_email, a.action, a.target, a.details, a.ip, a.user_agent, a.created_at
        from staff_audit_log a where {clause}
        order by a.created_at desc, a.id desc limit %s offset %s
        """,
        [*params, limit, offset],
    )
    total = fetch_one(f"select count(*) as n from staff_audit_log a where {clause}", params)["n"]
    return {"items": items, "total": total}


def _recent_failures(column: str, value: str | None) -> int:
    if not value:
        return 0
    expr = "lower(actor_email) = lower(%s)" if column == "email" else "ip = %s"
    return fetch_one(
        f"""
        select count(*) as c from staff_audit_log
        where action = 'auth.login_failed' and {expr}
          and created_at > now() - make_interval(mins => %s)
          and created_at > coalesce((
            select max(created_at) from staff_audit_log where action = 'auth.login' and {expr}
          ), '-infinity')
        """,
        (value, LOCKOUT_MINUTES, value),
    )["c"]


# ---------------------------------------------------------------- staff records


def get_staff(staff_id: str) -> dict | None:
    try:
        return fetch_one(f"select {STAFF_COLUMNS} from staff_users s where s.id = %s", (staff_id,))
    except Exception:  # malformed id
        return None


def get_staff_by_email(email: str) -> dict | None:
    return fetch_one(f"select {STAFF_COLUMNS}, s.password_hash from staff_users s where lower(s.email) = lower(%s)",
                     (email,))


def public_staff(staff: dict) -> dict:
    return {
        "id": str(staff["id"]),
        "email": staff["email"],
        "fullname": staff["fullname"],
        "status": staff["status"],
        "mustChangePassword": staff["must_change_password"],
    }


def me(staff_id: str) -> dict:
    staff = get_staff(staff_id)
    roles = access.staff_roles(staff_id)
    return {
        "user": public_staff(staff),
        "roles": [{"id": r["id"], "name": r["name"], "builtIn": bool(r["builtin_key"])} for r in roles],
        "permissions": sorted(access.staff_permissions(staff_id)),
        "superAdmin": any(r["builtin_key"] == access.SUPER_ADMIN for r in roles),
    }


# ---------------------------------------------------------------- sessions


def _new_session(staff: dict, client: ClientInfo, family_id: str | None = None, conn=None) -> tuple[str, str]:
    refresh = security.new_opaque_token()
    sql = """
        insert into staff_sessions (staff_id, family_id, refresh_hash, user_agent, ip, expires_at)
        values (%s, %s, %s, %s, %s, now() + make_interval(hours => %s))
        returning id::text
    """
    params = (staff["id"], family_id or str(uuid.uuid4()), security.token_hash(refresh),
              (client.user_agent or "")[:300] or None, client.ip, SESSION_TTL_HOURS)
    row = conn.execute(sql, params).fetchone() if conn else fetch_one(sql, params)
    return row["id"], refresh


def _session(staff: dict, client: ClientInfo) -> StaffSession:
    session_id, refresh = _new_session(staff, client)
    access_token, ttl = security.issue_staff_token(staff["id"], session_id)
    return StaffSession(public_staff(staff), access_token, ttl, refresh)


def login(email: str, password: str, client: ClientInfo) -> StaffSession:
    email = (email or "").strip()
    if (_recent_failures("email", email) >= MAX_FAILED_PER_EMAIL
            or _recent_failures("ip", client.ip) >= MAX_FAILED_PER_IP):
        audit("auth.login_blocked", actor_email=email, client=client)
        raise AuthError(f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.", 429)
    staff = get_staff_by_email(email)
    if not security.check_password(password, staff["password_hash"] if staff else None):
        audit("auth.login_failed", actor=staff, actor_email=email, client=client)
        raise AuthError("Incorrect email or password", 401)
    if staff["status"] != "active":
        audit("auth.login_failed", actor=staff, client=client, details={"reason": staff["status"]})
        raise AuthError("This staff account is not active. Ask a Super admin.", 403)
    execute("update staff_users set last_login_at = now() where id = %s", (staff["id"],))
    audit("auth.login", actor=staff, client=client)
    return _session(staff, client)


def refresh(refresh_token: str | None, client: ClientInfo) -> StaffSession:
    if not refresh_token:
        raise AuthError("Not signed in", 401)
    reused = None
    with connection() as conn, conn.transaction():
        session = conn.execute(
            """
            select s.id::text, s.staff_id::text, s.family_id::text, s.revoked_at, s.revoked_reason,
                   s.replaced_by::text, s.expires_at > now() as live,
                   s.revoked_at > now() - make_interval(secs => %s) as in_grace
            from staff_sessions s where s.refresh_hash = %s for update
            """,
            (ROTATION_GRACE_SECONDS, security.token_hash(refresh_token)),
        ).fetchone()
        if not session:
            raise AuthError("Session not found. Please sign in again.", 401)
        staff = get_staff(session["staff_id"])
        if session["revoked_at"] is not None:
            if session["revoked_reason"] == "rotated" and session["in_grace"] and session["replaced_by"]:
                replacement = conn.execute(
                    "select id::text from staff_sessions where id = %s and revoked_at is null",
                    (session["replaced_by"],),
                ).fetchone()
                if staff and staff["status"] == "active" and replacement:
                    token, ttl = security.issue_staff_token(staff["id"], replacement["id"])
                    return StaffSession(public_staff(staff), token, ttl, None)
            if session["revoked_reason"] != "rotated":
                raise AuthError("Your session has ended. Please sign in again.", 401)
            reused = session
        else:
            if not session["live"]:
                raise AuthError("Your session has expired. Please sign in again.", 401)
            if not staff or staff["status"] != "active":
                raise AuthError("This staff account is not active.", 401)
            # A rotation keeps the original sign-in's expiry: refreshing never extends a staff session
            new_refresh = security.new_opaque_token()
            new_row = conn.execute(
                """
                insert into staff_sessions (staff_id, family_id, refresh_hash, user_agent, ip, created_at, expires_at)
                select staff_id, family_id, %s, %s, %s, created_at, expires_at from staff_sessions where id = %s
                returning id::text
                """,
                (security.token_hash(new_refresh), (client.user_agent or "")[:300] or None, client.ip, session["id"]),
            ).fetchone()
            conn.execute(
                "update staff_sessions set revoked_at = now(), revoked_reason = 'rotated', replaced_by = %s where id = %s",
                (new_row["id"], session["id"]),
            )
    if reused:
        execute(
            "update staff_sessions set revoked_at = now(), revoked_reason = 'reuse_detected' "
            "where family_id = %s and revoked_at is null",
            (reused["family_id"],),
        )
        audit("auth.refresh_reuse", actor={"id": reused["staff_id"]}, client=client)
        raise AuthError("Your session has ended. Please sign in again.", 401)
    token, ttl = security.issue_staff_token(staff["id"], new_row["id"])
    return StaffSession(public_staff(staff), token, ttl, new_refresh)


def logout(refresh_token: str | None, session_id: str | None, client: ClientInfo) -> None:
    row = None
    if refresh_token:
        row = fetch_one(
            "update staff_sessions set revoked_at = now(), revoked_reason = 'logout' "
            "where refresh_hash = %s and revoked_at is null returning staff_id::text",
            (security.token_hash(refresh_token),),
        )
    if not row and session_id:
        row = fetch_one(
            "update staff_sessions set revoked_at = now(), revoked_reason = 'logout' "
            "where id = %s and revoked_at is null returning staff_id::text",
            (session_id,),
        )
    if row:
        audit("auth.logout", actor={"id": row["staff_id"], "email": (get_staff(row["staff_id"]) or {}).get("email")},
              client=client)


def revoke_session(session_id: str, staff_id: str, reason: str) -> bool:
    return fetch_one(
        "update staff_sessions set revoked_at = now(), revoked_reason = %s "
        "where id = %s and staff_id = %s and revoked_at is null returning id",
        (reason, session_id, staff_id),
    ) is not None


def revoke_all_sessions(staff_id: str, reason: str, keep_session_id: str | None = None) -> int:
    rows = fetch_all(
        """
        update staff_sessions set revoked_at = now(), revoked_reason = %s
        where staff_id = %s and revoked_at is null and (%s::uuid is null or id <> %s::uuid)
        returning id
        """,
        (reason, staff_id, keep_session_id, keep_session_id),
    )
    return len(rows)


_ACTIVE = "staff_id = %s and revoked_at is null and expires_at > now()"


def list_sessions(staff_id: str, limit: int = 10, offset: int = 0) -> dict:
    items = fetch_all(
        f"select id::text, user_agent, ip, created_at, last_used_at, expires_at from staff_sessions "
        f"where {_ACTIVE} order by created_at desc, id limit %s offset %s",
        (staff_id, limit, offset),
    )
    total = fetch_one(f"select count(*) as n from staff_sessions where {_ACTIVE}", (staff_id,))["n"]
    return {"items": items, "total": total}


def resolve_access_token(token: str) -> StaffActor | None:
    """The staff member behind an access token, if the token, session and account are all still valid."""
    claims = security.decode_staff_token(token)
    if not claims:
        return None
    try:
        row = fetch_one(
            """
            select s.id::text, s.email, s.fullname, s.must_change_password
            from staff_users s join staff_sessions ss on ss.staff_id = s.id
            where s.id = %s and ss.id = %s and s.status = 'active'
              and ss.revoked_at is null and ss.expires_at > now()
            """,
            (claims["sub"], claims["sid"]),
        )
    except Exception:
        return None
    if not row:
        return None
    return StaffActor(id=row["id"], email=row["email"], fullname=row["fullname"], session_id=claims["sid"],
                      permissions=access.staff_permissions(row["id"]),
                      must_change_password=row["must_change_password"])


# ---------------------------------------------------------------- one-time links


def issue_link(staff: dict, kind: str, created_by: str) -> str:
    """A fresh single-use link; any older unused link of the same kind stops working."""
    token = security.new_opaque_token()
    ttl_minutes = INVITE_TTL_HOURS * 60 if kind == "invite" else RESET_TTL_MINUTES
    execute("update staff_tokens set used_at = now() where staff_id = %s and kind = %s and used_at is null",
            (staff["id"], kind))
    execute(
        """
        insert into staff_tokens (staff_id, kind, token_hash, created_by, expires_at)
        values (%s, %s, %s, %s, now() + make_interval(mins => %s))
        """,
        (staff["id"], kind, security.token_hash(token), created_by, ttl_minutes),
    )
    page = "accept-invite" if kind == "invite" else "reset-password"
    return f"{settings.admin_base_url.rstrip('/')}/{page}?token={token}"


def revoke_links(staff_id: str, kind: str | None = None) -> int:
    rows = fetch_all(
        "update staff_tokens set used_at = now() where staff_id = %s and used_at is null "
        "and (%s::text is null or kind = %s) returning id",
        (staff_id, kind, kind),
    )
    return len(rows)


def pending_invite(staff_id: str) -> dict | None:
    return fetch_one(
        "select created_at, expires_at, expires_at < now() as expired from staff_tokens "
        "where staff_id = %s and kind = 'invite' and used_at is null order by created_at desc limit 1",
        (staff_id,),
    )


def check_link(token: str, kind: str) -> dict | None:
    """Who a link is for, without using it (the accept page shows the email)."""
    row = fetch_one(
        """
        select t.staff_id::text, s.email, s.fullname from staff_tokens t join staff_users s on s.id = t.staff_id
        where t.token_hash = %s and t.kind = %s and t.used_at is null and t.expires_at > now()
          and s.status <> 'disabled'
        """,
        (security.token_hash(token or ""), kind),
    )
    return row


def use_link(token: str, kind: str, new_password: str, client: ClientInfo) -> dict:
    """Set a password from an invitation or reset link. Single use; activates an invited account."""
    problem = security.password_problem(new_password)
    if problem:
        raise AuthError(problem, 422)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            """
            update staff_tokens t set used_at = now()
            from staff_users s
            where t.token_hash = %s and t.kind = %s and t.used_at is null and t.expires_at > now()
              and s.id = t.staff_id and s.status <> 'disabled'
            returning t.staff_id::text
            """,
            (security.token_hash(token or ""), kind),
        ).fetchone()
        if not row:
            raise AuthError("This link is invalid, already used or has expired. Ask a Super admin for a new one.", 400)
        conn.execute(
            """
            update staff_users set password_hash = %s, password_changed_at = now(), must_change_password = false,
              status = case when status = 'invited' then 'active' else status end, updated_at = now()
            where id = %s
            """,
            (security.hash_password(new_password), row["staff_id"]),
        )
    revoke_all_sessions(row["staff_id"], "password_reset")
    staff = get_staff(row["staff_id"])
    audit("auth.invite_accepted" if kind == "invite" else "auth.password_reset", actor=staff, client=client)
    return staff


def change_password(staff_id: str, current: str, new: str, session_id: str | None, client: ClientInfo) -> int:
    row = fetch_one("select password_hash, email from staff_users where id = %s", (staff_id,))
    if not row or not security.check_password(current, row["password_hash"]):
        audit("auth.password_change_failed", actor={"id": staff_id, "email": row and row["email"]}, client=client)
        raise AuthError("Current password is incorrect", 400)
    problem = security.password_problem(new)
    if problem:
        raise AuthError(problem, 422)
    if current == new:
        raise AuthError("The new password must be different", 422)
    execute(
        "update staff_users set password_hash = %s, password_changed_at = now(), must_change_password = false, "
        "updated_at = now() where id = %s",
        (security.hash_password(new), staff_id),
    )
    signed_out = revoke_all_sessions(staff_id, "password_changed", keep_session_id=session_id)
    audit("auth.password_changed", actor={"id": staff_id, "email": row["email"]}, client=client,
          details={"other_sessions_signed_out": signed_out})
    return signed_out


# ---------------------------------------------------------------- email


def send_email(to: str, subject: str, body: str) -> bool:
    """SMTP when configured; otherwise the message goes to the API log so a developer can use the link."""
    if not settings.smtp_host:
        log.warning("Email to %s (no SMTP configured): %s\n%s", to, subject, body)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("Could not send email to %s", to)
        return False


def send_invite(staff: dict, link: str, invited_by: str) -> bool:
    return send_email(
        staff["email"],
        "You have been invited to the Compliance Navigator staff workspace",
        f"Hello {staff['fullname'] or ''},\n\n"
        f"{invited_by} invited you to the Compliance Navigator staff workspace.\n\n"
        f"Sign-in email: {staff['email']}\n"
        f"Choose your password here within {INVITE_TTL_HOURS} hours (the link works once):\n{link}\n\n"
        f"After that, sign in at {settings.admin_base_url.rstrip('/')}/login\n\n"
        "If you were not expecting this, ignore this email.\n",
    )


def send_reset(staff: dict, link: str) -> bool:
    return send_email(
        staff["email"],
        "Reset your Compliance Navigator staff password",
        f"Hello {staff['fullname'] or ''},\n\n"
        f"Use this link within {RESET_TTL_MINUTES} minutes to choose a new staff password (it works once):\n{link}\n\n"
        f"Sign-in email: {staff['email']}\n\n"
        "If you didn't expect this, tell a Super admin.\n",
    )
