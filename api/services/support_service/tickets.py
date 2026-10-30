"""The customer side: opening tickets, replying and reading one's own tickets."""

from __future__ import annotations

from services.db import Jsonb, connection, fetch_all, fetch_one
from services import platform_settings
from .common import (
    PRIORITIES,
    QUEUES,
    REOPEN_DAYS,
    SLA_HOURS,
    TICKET_SELECT,
    SupportError,
    _add_message,
    _shape,
    get,
    guess_priority,
)


# ---------------------------------------------------------------- customers


def create_ticket(
    *, subject: str, body: str, queue: str = "customer_support", priority: str | None = None,
    source: str = "contact_form", user_id: str | None = None, name: str | None = None, phone: str | None = None,
    email: str | None = None, conversation_id: str | None = None, service_key: str | None = None,
    service_title: str | None = None, context: dict | None = None, category: str | None = None, ip: str | None = None,
    follow_up_of: str | None = None,
) -> dict:
    if queue not in QUEUES:
        raise SupportError("Unknown team")
    subject, body = (subject or "").strip(), (body or "").strip()
    if not subject or not body:
        raise SupportError("Tell us what you need help with")
    if not user_id and not (name and (phone or email)):
        raise SupportError("Leave your name and a phone number or email so we can reach you")
    if follow_up_of:
        # Only the owner can link a new request to an older one
        older = get_for_user(follow_up_of, user_id) if user_id else None
        if not older:
            raise SupportError("The earlier request was not found", 404)
        follow_up_of = older["id"]
    if ip:
        recent = fetch_one(
            "select count(*) as c from support_tickets where ip = %s and created_at > now() - interval '1 hour'", (ip,)
        )["c"]
        if recent >= platform_settings.get_int("support_tickets_per_ip_hour"):
            raise SupportError("Too many requests from this connection. Please try again later.", 429)
    if user_id and not (name and phone):
        u = fetch_one("select fullname, phone, email from users where id = %s", (user_id,)) or {}
        name = name or u.get("fullname") or None
        phone = phone or u.get("phone")
        email = email or u.get("email")
    priority = priority if priority in PRIORITIES else guess_priority(f"{subject} {body}")
    with connection() as conn, conn.transaction():
        row = conn.execute(
            """
            insert into support_tickets (user_id, contact_name, contact_phone, contact_email, queue, category, subject,
              priority, source, conversation_id, service_key, service_title, context, ip, follow_up_of,
              sla_due_at, next_response_due_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    now() + make_interval(hours => %s), now() + make_interval(hours => %s))
            returning id::text
            """,
            (user_id, name, phone, email, queue, category, subject[:200], priority, source, conversation_id,
             service_key, service_title, Jsonb(context or {}), ip, follow_up_of, SLA_HOURS[priority], SLA_HOURS[priority]),
        ).fetchone()
        ticket_id = row["id"]
        _add_message(conn, ticket_id, "customer", body[:4000], user_id)
    return get(ticket_id)


def list_for_user(user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    return [_shape(r) for r in fetch_all(f"{TICKET_SELECT} where t.user_id = %s order by t.updated_at desc limit %s offset %s",
                                         (user_id, limit, offset))]


def count_for_user(user_id: str) -> int:
    return fetch_one("select count(*) as c from support_tickets where user_id = %s", (user_id,))["c"]


def get_for_user(ticket_id: str, user_id: str) -> dict | None:
    ticket = get(ticket_id)
    return ticket if ticket and ticket["user_id"] == user_id else None


def customer_reply(ticket_id: str, user_id: str | None, body: str) -> dict:
    """A customer writes on their ticket. A resolved or closed one reopens if it ended in the last 7 days."""
    body = (body or "").strip()
    if not body:
        raise SupportError("Write a message first")
    with connection() as conn, conn.transaction():
        t = conn.execute(
            f"""
            select status, priority,
                   coalesce(resolved_at, updated_at) > now() - make_interval(days => {REOPEN_DAYS}) as reopenable
            from support_tickets where id = %s for update
            """,
            (ticket_id,),
        ).fetchone()
        if not t:
            raise SupportError("Request not found", 404)
        reopening = t["status"] in ("resolved", "closed")
        if reopening and not t["reopenable"]:
            raise SupportError(
                f"This request ended more than {REOPEN_DAYS} days ago, so it can't be reopened. "
                "Please send a new request; we will link it to this one.", 409)
        _add_message(conn, ticket_id, "customer", body[:4000], user_id)
        if reopening:
            _add_message(conn, ticket_id, "system", "Reopened by the customer's reply.", None, True)
        # A new customer message starts a new reply deadline, unless one is already running
        conn.execute(
            """
            update support_tickets set updated_at = now(), resolved_at = null,
              status = case when status = 'new' then 'new' else 'open' end,
              next_response_due_at = case when status in ('new', 'open') and next_response_due_at is not null
                                          then next_response_due_at else now() + make_interval(hours => %s) end
            where id = %s
            """,
            (SLA_HOURS[t["priority"]], ticket_id),
        )
    return get(ticket_id)


def open_ticket_for_conversation(conversation_id: str) -> dict | None:
    row = fetch_one(
        "select id::text from support_tickets where conversation_id = %s order by created_at desc limit 1",
        (conversation_id,),
    )
    return get(row["id"]) if row else None


def brief(ticket: dict | None) -> dict | None:
    if not ticket:
        return None
    return {k: ticket[k] for k in ("id", "ref", "status", "status_label", "queue", "queue_label")}
