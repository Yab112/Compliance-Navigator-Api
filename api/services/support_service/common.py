"""Queues, priorities and the ticket reads and helpers shared by the customer and staff sides."""

from __future__ import annotations

import os
import re
import uuid

from services.db import fetch_all, fetch_one


QUEUES = {
    "customer_support": ("General help", "አጠቃላይ እገዛ",
                         "Anything else: how the platform works, where to start, feedback."),
    "compliance": ("Compliance and requirements", "ተገዢነት እና መስፈርቶች",
                   "Which licence, permit or document you need, and what an office will ask for."),
    "marketplace": ("Providers and hires", "አገልግሎት ሰጪዎች",
                    "Finding an agent or agency, problems with a hire, refunds and disputes."),
    "organizations": ("Organizations and service data", "ተቋማት",
                      "Wrong or outdated information, and organizations publishing their services."),
    "technical": ("Account and website", "መለያ እና ድረ-ገጽ",
                  "Signing in, verification, errors on the site."),
}
STATUS_LABELS = {
    "new": "New", "open": "Open", "waiting_customer": "Waiting for your reply",
    "resolved": "Resolved", "closed": "Closed",
}
ACTIVE = ("new", "open", "waiting_customer")
PRIORITIES = ("low", "normal", "high", "urgent")
SLA_HOURS = {"urgent": 2, "high": 8, "normal": 24, "low": 72}
PRIORITY_ORDER = "case t.priority when 'urgent' then 0 when 'high' then 1 when 'normal' then 2 else 3 end"

CONTACT = {
    "phone": os.environ.get("SUPPORT_PHONE", "+251 11 000 0000"),
    "email": os.environ.get("SUPPORT_EMAIL", "support@compliance-navigator.et"),
    "hours": os.environ.get("SUPPORT_HOURS", "Monday to Friday, 8:30 to 17:30 · Saturday 8:30 to 12:30"),
    "hours_am": os.environ.get("SUPPORT_HOURS_AM", "ከሰኞ እስከ አርብ 2:30 እስከ 11:30 · ቅዳሜ 2:30 እስከ 6:30"),
    "address": os.environ.get("SUPPORT_ADDRESS", "Bole, Addis Ababa"),
    "address_am": os.environ.get("SUPPORT_ADDRESS_AM", "ቦሌ፣ አዲስ አበባ"),
}

_URGENT = re.compile(r"\b(urgent|asap|emergency|today|tomorrow|deadline|immediately)\b|አስቸኳይ|ዛሬ|ነገ", re.I)


class SupportError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def queue_label(key: str) -> str:
    return QUEUES.get(key, QUEUES["customer_support"])[0]


def expected_text(priority: str) -> str:
    hours = SLA_HOURS.get(priority, 24)
    return f"Usually within {hours} hours" if hours < 24 else f"Usually within {hours // 24} working day{'s' if hours > 24 else ''}"


def guess_priority(text: str) -> str:
    return "high" if _URGENT.search(text or "") else "normal"


def meta() -> dict:
    return {
        "queues": [{"key": k, "label": v[0], "label_am": v[1], "description": v[2]} for k, v in QUEUES.items()],
        "contact": CONTACT,
    }


REOPEN_DAYS = 7
# We owe the customer an answer and the deadline has passed
OVERDUE_SQL = "(t.status in ('new', 'open') and t.next_response_due_at < now())"

TICKET_FROM = """
from support_tickets t
left join users u on u.id = t.user_id
left join staff_users a on a.id = t.assignee_id
left join support_tickets fu on fu.id = t.follow_up_of
left join lateral (
  select body, created_at, author_kind from support_messages m
  where m.ticket_id = t.id and not m.internal and m.author_kind in ('customer', 'staff')
  order by m.id desc limit 1
) lm on true
"""

TICKET_SELECT = f"""
select t.id::text, t.ref, t.subject, t.queue, t.status, t.priority, t.source, t.category,
       t.contact_name, t.contact_phone, t.contact_email, t.user_id::text, u.email as user_email,
       t.conversation_id::text, t.service_key, t.service_title, t.context,
       t.assignee_id::text, nullif(a.fullname, '') as assignee_name, a.email as assignee_email,
       t.created_at, t.updated_at, t.first_response_at, t.resolved_at, t.sla_due_at, t.next_response_due_at,
       t.follow_up_of::text, fu.ref as follow_up_of_ref,
       {OVERDUE_SQL} as overdue,
       lm.body as last_message_preview, lm.created_at as last_message_at,
       coalesce(lm.author_kind = 'customer', true) as awaiting_staff,
       (t.status in ('resolved', 'closed')
        and coalesce(t.resolved_at, t.updated_at) > now() - make_interval(days => {REOPEN_DAYS})) as can_reopen,
       case when t.status in ('resolved', 'closed')
            then coalesce(t.resolved_at, t.updated_at) + make_interval(days => {REOPEN_DAYS}) end as reopen_until,
       (select count(*) from support_messages m where m.ticket_id = t.id and not m.internal) as message_count
{TICKET_FROM}"""


def _shape(row: dict | None) -> dict | None:
    if not row:
        return None
    row["queue_label"] = queue_label(row["queue"])
    row["status_label"] = STATUS_LABELS[row["status"]]
    row["assignee_name"] = row.pop("assignee_name") or row.pop("assignee_email", None)
    row.pop("assignee_email", None)
    if row["last_message_preview"]:
        row["last_message_preview"] = row["last_message_preview"][:160]
    row["awaiting_staff"] = bool(row["awaiting_staff"]) and row["status"] in ACTIVE
    # Who has to act next, and since when (the age of the last public message)
    row["waiting_on"] = ("us" if row["awaiting_staff"] else "customer") if row["status"] in ACTIVE else None
    row["waiting_since"] = row["last_message_at"] or row["created_at"]
    return row


def get(ticket_id: str) -> dict | None:
    try:
        return _shape(fetch_one(f"{TICKET_SELECT} where t.id = %s", (ticket_id,)))
    except Exception:  # malformed id
        return None


def messages(ticket_id: str, *, include_internal: bool) -> list[dict]:
    internal = "" if include_internal else "and not m.internal"
    # Customer messages are written by public accounts, staff and system ones by staff accounts
    return fetch_all(
        f"""
        select m.id, m.author_kind,
               case when m.author_kind = 'customer' then coalesce(nullif(u.fullname, ''), u.email)
                    else coalesce(nullif(s.fullname, ''), s.email, nullif(u.fullname, ''), u.email) end as author_name,
               m.body, m.internal, m.created_at
        from support_messages m
        left join users u on u.id = m.author_id
        left join staff_users s on s.id = m.author_id and m.author_kind <> 'customer'
        where m.ticket_id = %s {internal} order by m.id
        """,
        (ticket_id,),
    )


def _add_message(conn, ticket_id: str, kind: str, body: str, author_id: str | None = None, internal: bool = False):
    conn.execute(
        "insert into support_messages (ticket_id, author_kind, author_id, body, internal) values (%s, %s, %s, %s, %s)",
        (ticket_id, kind, author_id, body, internal),
    )


def log_staff_action(action: str, author: dict, target: str, details: dict, client=None) -> None:
    """An extra, more detailed staff audit entry (require_admin already logs every change request)."""
    from auth.staff_service import audit

    audit(action, actor={"id": author.get("id"), "email": author.get("email")}, target=target,
          details=details, client=client)


def _like(text: str) -> str:
    return "%" + text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False
