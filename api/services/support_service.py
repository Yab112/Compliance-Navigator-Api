"""Support desk: requests from the assistant's handoff, the contact form and reports, worked by staff.

A ticket belongs to one queue (the team that answers it). Staff replies notify the customer and,
when the ticket came from the chat, appear in that chat conversation as a `staff` message.
"""

from __future__ import annotations

import os
import re
import uuid

from psycopg import errors as pg_errors

from services import notifications
from services.db import Jsonb, connection, execute, fetch_all, fetch_one
from services import platform_settings

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


# ---------------------------------------------------------------- staff


def staff() -> list[dict]:
    """Active staff who can answer tickets (the people a ticket can be assigned to)."""
    rows = fetch_all(
        "select id::text, coalesce(nullif(fullname, ''), email) as name from staff_users where status = 'active' order by 2"
    )
    from services import access

    allowed = {r["id"] for r in access.holders_of("support.reply")}
    return [r for r in rows if r["id"] in allowed]


STATUS_FILTERS = ("active", "overdue", "all", *STATUS_LABELS)
SORTS = {
    # Late first, then by priority, then whoever has waited longest
    "triage": f"{OVERDUE_SQL} desc, {PRIORITY_ORDER}, coalesce(t.next_response_due_at, t.created_at)",
    "newest": "t.created_at desc",
    "oldest": "t.created_at",
    "updated": "coalesce(lm.created_at, t.updated_at) desc",
}


def _like(text: str) -> str:
    return "%" + text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _filters(*, queue: str | None = None, status: str | None = "active", assigned: str | None = None,
             priority: str | None = None, source: str | None = None, waiting: str | None = None,
             q: str | None = None, since: str | None = None, until: str | None = None,
             staff_id: str | None = None) -> tuple[str, dict]:
    where, params = ["true"], {}
    if queue:
        where.append("t.queue = %(queue)s")
        params["queue"] = queue
    if status == "active" or not status:
        where.append("t.status in ('new', 'open', 'waiting_customer')")
    elif status == "overdue":
        where.append(OVERDUE_SQL)
    elif status != "all":
        where.append("t.status = %(status)s")
        params["status"] = status
    if assigned == "me":
        where.append("t.assignee_id = %(me)s")
        params["me"] = staff_id
    elif assigned == "none":
        where.append("t.assignee_id is null")
    elif assigned:
        where.append("t.assignee_id::text = %(assignee)s")
        params["assignee"] = assigned
    if priority:
        where.append("t.priority = %(priority)s")
        params["priority"] = priority
    if source:
        where.append("t.source = %(source)s")
        params["source"] = source
    if waiting == "us":
        where.append("t.status in ('new', 'open', 'waiting_customer') and coalesce(lm.author_kind = 'customer', true)")
    elif waiting == "customer":
        where.append("t.status in ('new', 'open', 'waiting_customer') and lm.author_kind = 'staff'")
    if since:
        where.append("t.created_at >= %(since)s::date")
        params["since"] = since
    if until:
        where.append("t.created_at < %(until)s::date + 1")
        params["until"] = until
    if q and q.strip():
        where.append(
            "(t.ref ilike %(q)s or t.subject ilike %(q)s or t.contact_name ilike %(q)s or t.contact_phone ilike %(q)s "
            "or t.contact_email ilike %(q)s or u.email ilike %(q)s "
            "or exists (select 1 from support_messages sm where sm.ticket_id = t.id and sm.body ilike %(q)s))"
        )
        params["q"] = _like(q)
    return " and ".join(where), params


def admin_list(*, sort: str = "triage", limit: int = 25, offset: int = 0, **filters) -> dict:
    clause, params = _filters(**filters)
    total = fetch_one(f"select count(*) as c {TICKET_FROM} where {clause}", params)["c"]
    rows = fetch_all(
        f"""{TICKET_SELECT} where {clause}
        order by {SORTS.get(sort, SORTS['triage'])}, t.id
        limit %(limit)s offset %(offset)s""",
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": [_shape(r) for r in rows]}


EXPORT_LIMIT = 5000
EXPORT_COLUMNS = [
    ("ref", "Ref"), ("subject", "Subject"), ("queue_label", "Team"), ("status_label", "Status"),
    ("priority", "Priority"), ("source", "Source"), ("contact_name", "Contact name"), ("contact_phone", "Contact phone"),
    ("contact_email", "Contact email"), ("user_email", "Account email"), ("assignee_name", "Assignee"),
    ("waiting_on", "Waiting on"), ("overdue", "Overdue"), ("created_at", "Opened"),
    ("first_response_at", "First reply"), ("next_response_due_at", "Reply due"), ("resolved_at", "Resolved"),
    ("message_count", "Messages"),
]


def csv_cell(value) -> str:
    """Text for one CSV cell. A leading = + - @ (or tab, carriage return) would run as a formula in a
    spreadsheet, so such cells get a leading apostrophe."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if hasattr(value, "isoformat"):
        return value.isoformat(timespec="minutes") if hasattr(value, "hour") else value.isoformat()
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(*, sort: str = "triage", **filters) -> tuple[str, int]:
    """The filtered list as CSV (at most EXPORT_LIMIT rows). Returns the text and the row count."""
    import csv
    import io

    data = admin_list(sort=sort, limit=EXPORT_LIMIT, offset=0, **filters)
    out = io.StringIO()
    out.write("﻿")  # so spreadsheet programs read Amharic correctly
    writer = csv.writer(out)
    writer.writerow([label for _, label in EXPORT_COLUMNS])
    for row in data["items"]:
        writer.writerow([csv_cell(row.get(key)) for key, _ in EXPORT_COLUMNS])
    return out.getvalue(), len(data["items"])


def transcript(conversation_id: str | None) -> list[dict]:
    if not conversation_id:
        return []
    return [
        {"role": r["role"], "text": r["content"], "created_at": r["created_at"]}
        for r in fetch_all(
            "select role, content, created_at from assistant_messages where conversation_id = %s order by id limit 200",
            (conversation_id,),
        )
    ]


def admin_detail(ticket_id: str) -> dict | None:
    ticket = get(ticket_id)
    if not ticket:
        return None
    return {"ticket": ticket, "messages": messages(ticket_id, include_internal=True),
            "transcript": transcript(ticket["conversation_id"]), "staff": staff()}


def _tell(ticket: dict, kind: str, title: str, body: str | None) -> None:
    if ticket["user_id"]:
        notifications.notify([ticket["user_id"]], kind=kind, title=title, body=body,
                             link=f"/account/support/{ticket['id']}")


def staff_reply(ticket_id: str, *, author: dict, body: str, internal: bool = False, resolve: bool = False,
                canned_reply_id: str | None = None) -> dict:
    """author: {id, name, email}. With resolve, the reply and the resolve happen together or not at all."""
    from assistant import store

    ticket = get(ticket_id)
    if not ticket:
        raise SupportError("Request not found", 404)
    body = (body or "").strip()
    if not body:
        raise SupportError("Write a message first")
    if internal and resolve:
        raise SupportError("Send a reply to the customer to resolve the request")
    resolve = resolve and ticket["status"] not in ("resolved", "closed")
    with connection() as conn, conn.transaction():
        _add_message(conn, ticket_id, "staff", body[:4000], author["id"], internal)
        if not internal:
            conn.execute(
                """
                update support_tickets set updated_at = now(), first_response_at = coalesce(first_response_at, now()),
                  next_response_due_at = null,
                  status = case when %(resolve)s then 'resolved'
                                when status in ('resolved', 'closed') then status else 'waiting_customer' end,
                  resolved_at = case when %(resolve)s then now() else resolved_at end,
                  assignee_id = coalesce(assignee_id, %(author)s)
                where id = %(id)s
                """,
                {"resolve": resolve, "author": author["id"], "id": ticket_id},
            )
            if resolve:
                _add_message(conn, ticket_id, "system", f"Status changed to resolved by {author['name']}.", author["id"], True)
        else:
            conn.execute("update support_tickets set updated_at = now() where id = %s", (ticket_id,))
        if canned_reply_id and _is_uuid(canned_reply_id):
            conn.execute("update support_canned_replies set use_count = use_count + 1 where id = %s", (canned_reply_id,))
    if not internal:
        team = ticket["queue_label"]
        if ticket["conversation_id"]:
            store.add_message(ticket["conversation_id"], "staff", body,
                              {"staff": {"name": author["name"], "team": team}, "ticket": ticket["ref"]})
        title = f"{team} replied and resolved {ticket['ref']}" if resolve else f"{team} replied to {ticket['ref']}"
        _tell(ticket, "support_reply", title, body[:140])
    return admin_detail(ticket_id)


def update(ticket_id: str, data: dict, *, author: dict, client=None) -> dict:
    ticket = get(ticket_id)
    if not ticket:
        raise SupportError("Request not found", 404)
    sets, params, notes, changes = [], [], [], {}
    new_status = data.get("status")
    if new_status and new_status != ticket["status"]:
        if new_status not in STATUS_LABELS:
            raise SupportError("Unknown status")
        sets.append("status = %s")
        params.append(new_status)
        if new_status in ("resolved", "closed"):
            # The reopen window counts from the first time it ended
            sets += ["resolved_at = coalesce(resolved_at, now())", "next_response_due_at = null"]
        elif new_status == "waiting_customer":
            sets += ["resolved_at = null", "next_response_due_at = null"]
        else:
            # Back on our desk: we owe them an answer again
            sets += ["resolved_at = null",
                     "next_response_due_at = coalesce(next_response_due_at, now() + make_interval(hours => %s))"]
            params.append(SLA_HOURS[data.get("priority") or ticket["priority"]])
        notes.append(f"Status changed to {STATUS_LABELS[new_status].lower()}")
        changes["status"] = [ticket["status"], new_status]
    if data.get("priority") and data["priority"] != ticket["priority"]:
        if data["priority"] not in PRIORITIES:
            raise SupportError("Unknown priority")
        hours = SLA_HOURS[data["priority"]]
        # The running deadline moves too: counted from the customer's latest message
        sets += ["priority = %s", "sla_due_at = created_at + make_interval(hours => %s)",
                 """next_response_due_at = case when next_response_due_at is null then null else coalesce(
                      (select max(m.created_at) from support_messages m
                       where m.ticket_id = support_tickets.id and m.author_kind = 'customer' and not m.internal),
                      created_at) + make_interval(hours => %s) end"""]
        params += [data["priority"], hours, hours]
        notes.append(f"Priority set to {data['priority']}")
        changes["priority"] = [ticket["priority"], data["priority"]]
    if data.get("queue") and data["queue"] != ticket["queue"]:
        if data["queue"] not in QUEUES:
            raise SupportError("Unknown team")
        sets.append("queue = %s")
        params.append(data["queue"])
        notes.append(f"Moved to {queue_label(data['queue'])}")
        changes["queue"] = [ticket["queue"], data["queue"]]
    if "assignee_id" in data and data["assignee_id"] != ticket["assignee_id"]:
        people = staff()
        if data["assignee_id"] and not any(s["id"] == data["assignee_id"] for s in people):
            raise SupportError("Can only assign to staff who answer tickets")
        sets.append("assignee_id = %s")
        params.append(data["assignee_id"])
        name = next((s["name"] for s in people if s["id"] == data["assignee_id"]), None)
        notes.append(f"Assigned to {name}" if name else "Unassigned")
        changes["assignee"] = [ticket["assignee_name"], name]
    if sets:
        if ticket["status"] == "new" and "status" not in changes:
            sets.append("status = 'open'")
        with connection() as conn, conn.transaction():
            conn.execute(f"update support_tickets set {', '.join(sets)}, updated_at = now() where id = %s",
                         (*params, ticket_id))
            _add_message(conn, ticket_id, "system", f"{'. '.join(notes)} by {author['name']}.", author["id"], True)
        log_staff_action("support.ticket.update", author, ticket["ref"], changes, client)
        # Tell the customer about changes that matter to them; assignment and priority stay internal
        was_done = ticket["status"] in ("resolved", "closed")
        if new_status == "resolved" and ticket["status"] != "resolved":
            _tell(ticket, "support_resolved", f"{ticket['ref']} was resolved", ticket["subject"])
        elif new_status == "closed" and ticket["status"] != "closed":
            _tell(ticket, "support_resolved", f"{ticket['ref']} was closed", ticket["subject"])
        elif was_done and new_status in ("new", "open", "waiting_customer"):
            _tell(ticket, "support_reply", f"{ticket['ref']} was reopened", "Our team is looking at it again.")
        if "queue" in changes and new_status not in ("resolved", "closed"):
            _tell(ticket, "support_reply", f"{ticket['ref']} moved to {queue_label(data['queue'])}",
                  "That team will answer you from now on.")
    return admin_detail(ticket_id)


# ---------------------------------------------------------------- customer context


def customer_context(ticket_id: str, *, can=None) -> dict | None:
    """What staff need to know about the person behind a ticket: their account, hires, payments and
    other requests. Hires and payments are left out for staff without those permissions. No ID numbers,
    addresses, payout details or gateway data."""
    can = can or (lambda _permission: True)
    t = fetch_one("select id::text, user_id::text, contact_phone, contact_email from support_tickets where id = %s",
                  (ticket_id,)) if _is_uuid(ticket_id) else None
    if not t:
        return None
    out: dict = {"account": None, "provider": None, "hires": None, "payments": None, "hidden": []}
    uid = t["user_id"]
    if uid:
        out["account"] = fetch_one(
            """
            select u.id::text, coalesce(nullif(u.fullname, ''), u.email) as name, u.email, u.phone, u.role, u.is_active,
                   u.created_at, u.last_login_at,
                   (select count(*) from roadmaps r where r.user_id = u.id) as roadmaps
            from users u where u.id = %s
            """,
            (uid,),
        )
        out["provider"] = fetch_one(
            "select id::text, display_name, status, provider_type from providers where user_id = %s limit 1", (uid,))
        if can("hires.view"):
            out["hires"] = {
                "items": fetch_all(
                    """
                    select e.id::text, coalesce(nullif(e.title, ''), e.service_name, 'Hire') as title, e.status,
                           e.payment_status, e.disputed, e.dispute_status, e.agreed_price, e.created_at,
                           p.display_name as provider_name
                    from engagements e left join providers p on p.id = e.provider_id
                    where e.client_user_id = %s and not coalesce(e.is_sample, false)
                    order by e.created_at desc limit 5
                    """,
                    (uid,),
                ),
                "total": fetch_one("select count(*) as c from engagements where client_user_id = %s "
                                   "and not coalesce(is_sample, false)", (uid,))["c"],
            }
        else:
            out["hidden"].append("hires")
        if can("payments.view"):
            out["payments"] = {
                "items": fetch_all(
                    """
                    select p.tx_ref, p.amount, p.currency, p.status, p.created_at, p.verified_at,
                           coalesce(nullif(e.title, ''), e.service_name) as hire_title
                    from payments p left join engagements e on e.id = p.engagement_id
                    where p.payer_user_id = %s order by p.created_at desc limit 5
                    """,
                    (uid,),
                ),
                "total": fetch_one("select count(*) as c from payments where payer_user_id = %s", (uid,))["c"],
            }
        else:
            out["hidden"].append("payments")
        other, params = "t.user_id = %(uid)s", {"uid": uid}
    else:
        # No account: other requests left with the same phone or email
        conds, params = [], {}
        if t["contact_phone"]:
            conds.append("t.contact_phone = %(phone)s")
            params["phone"] = t["contact_phone"]
        if t["contact_email"]:
            conds.append("lower(t.contact_email) = lower(%(email)s)")
            params["email"] = t["contact_email"]
        other = f"({' or '.join(conds)})" if conds else "false"
    params["id"] = t["id"]
    out["tickets"] = {
        "items": fetch_all(
            f"""
            select t.id::text, t.ref, t.subject, t.status, t.queue, t.created_at from support_tickets t
            where {other} and t.id <> %(id)s order by t.created_at desc limit 5
            """,
            params,
        ),
        "total": fetch_one(f"select count(*) as c from support_tickets t where {other} and t.id <> %(id)s", params)["c"],
    }
    for item in out["tickets"]["items"]:
        item["status_label"] = STATUS_LABELS[item["status"]]
        item["queue_label"] = queue_label(item["queue"])
    return out


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- saved replies

PLACEHOLDERS = {
    "name": "The customer's first name",
    "ref": "The request number, like CN-001234",
    "subject": "The request's subject",
    "team": "The team that has the request",
    "agent": "Your name",
}
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_]+)\s*\}\}")
REPLY_SELECT = ("select id::text, title, body, queue, use_count, created_by_name, updated_by_name, created_at, updated_at "
                "from support_canned_replies")


def _check_reply(data: dict) -> dict:
    title, body = (data.get("title") or "").strip(), (data.get("body") or "").strip()
    if len(title) < 3:
        raise SupportError("Give the reply a short title")
    if not body:
        raise SupportError("Write the reply text")
    unknown = sorted({m.group(1) for m in _PLACEHOLDER.finditer(body)} - set(PLACEHOLDERS))
    if unknown:
        raise SupportError(f"Unknown placeholder {{{{{unknown[0]}}}}}. You can use: "
                           + ", ".join(f"{{{{{k}}}}}" for k in PLACEHOLDERS))
    queue = data.get("queue") or None
    if queue and queue not in QUEUES:
        raise SupportError("Unknown team")
    return {"title": title[:120], "body": body[:4000], "queue": queue}


def render_reply(body: str, ticket: dict, agent_name: str | None) -> str:
    first = (ticket.get("contact_name") or "").strip().split(" ")[0]
    values = {"name": first or "there", "ref": ticket["ref"], "subject": ticket["subject"],
              "team": ticket["queue_label"], "agent": agent_name or "Support team"}
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), body)


def list_replies(*, queue: str | None = None, q: str | None = None, ticket_id: str | None = None,
                 agent_name: str | None = None, limit: int = 25, offset: int = 0) -> dict:
    """Saved replies, most used first. With ticket_id: only those for that ticket's team, filled in."""
    ticket = get(ticket_id) if ticket_id else None
    if ticket_id and not ticket:
        raise SupportError("Request not found", 404)
    where, params = ["true"], {}
    if ticket:
        where.append("(queue is null or queue = %(queue)s)")
        params["queue"] = ticket["queue"]
    elif queue:
        where.append("queue = %(queue)s")
        params["queue"] = queue
    if q and q.strip():
        where.append("(title ilike %(q)s or body ilike %(q)s)")
        params["q"] = _like(q)
    clause = " and ".join(where)
    items = fetch_all(f"{REPLY_SELECT} where {clause} order by use_count desc, lower(title) limit %(limit)s offset %(offset)s",
                      {**params, "limit": limit, "offset": offset})
    for item in items:
        item["queue_label"] = queue_label(item["queue"]) if item["queue"] else None
        if ticket:
            item["rendered"] = render_reply(item["body"], ticket, agent_name)
    total = fetch_one(f"select count(*) as c from support_canned_replies where {clause}", params)["c"]
    return {"items": items, "total": total, "placeholders": PLACEHOLDERS}


_DUPLICATE_TITLE = "A saved reply with this title already exists"


def create_reply(data: dict, *, author: dict) -> dict:
    clean = _check_reply(data)
    try:
        row = fetch_one(
            """
            insert into support_canned_replies (title, body, queue, created_by, created_by_name, updated_by_name)
            values (%s, %s, %s, %s, %s, %s) returning id::text
            """,
            (clean["title"], clean["body"], clean["queue"], author["id"], author["name"], author["name"]),
        )
    except pg_errors.UniqueViolation:
        raise SupportError(_DUPLICATE_TITLE, 409) from None
    return fetch_one(f"{REPLY_SELECT} where id = %s", (row["id"],))


def update_reply(reply_id: str, data: dict, *, author: dict) -> dict:
    if not _is_uuid(reply_id) or not fetch_one("select 1 from support_canned_replies where id = %s", (reply_id,)):
        raise SupportError("Saved reply not found", 404)
    clean = _check_reply(data)
    try:
        execute(
            "update support_canned_replies set title = %s, body = %s, queue = %s, updated_by_name = %s, updated_at = now() "
            "where id = %s",
            (clean["title"], clean["body"], clean["queue"], author["name"], reply_id),
        )
    except pg_errors.UniqueViolation:
        raise SupportError(_DUPLICATE_TITLE, 409) from None
    return fetch_one(f"{REPLY_SELECT} where id = %s", (reply_id,))


def delete_reply(reply_id: str, *, author: dict) -> None:
    row = fetch_one("delete from support_canned_replies where id = %s returning title", (reply_id,)) \
        if _is_uuid(reply_id) else None
    if not row:
        raise SupportError("Saved reply not found", 404)


# ---------------------------------------------------------------- summary


def summary(staff_id: str | None) -> dict:
    from services import provider_service

    totals = fetch_one(
        f"""
        select count(*) filter (where t.status = 'new') as new,
               count(*) filter (where t.status = 'open') as open,
               count(*) filter (where t.status = 'waiting_customer') as waiting_customer,
               count(*) filter (where {OVERDUE_SQL}) as overdue,
               count(*) filter (where t.status in ('new', 'open', 'waiting_customer') and t.assignee_id is null) as unassigned,
               count(*) filter (where t.status in ('new', 'open', 'waiting_customer') and t.assignee_id = %s) as mine,
               count(*) filter (where t.status in ('resolved', 'closed') and t.resolved_at > now() - interval '7 days') as resolved_7d,
               round(avg(extract(epoch from t.first_response_at - t.created_at) / 60)
                     filter (where t.first_response_at > now() - interval '30 days'))::int as avg_first_response_minutes
        from support_tickets t
        """,
        (staff_id,),
    )
    by_queue = {
        r["queue"]: r for r in fetch_all(
            f"""
            select t.queue, count(*) filter (where t.status in ('new', 'open', 'waiting_customer')) as open,
                   count(*) filter (where t.status in ('new', 'open', 'waiting_customer') and t.assignee_id is null) as unassigned,
                   count(*) filter (where {OVERDUE_SQL}) as overdue
            from support_tickets t group by t.queue
            """
        )
    }
    queues = [{"key": k, "label": v[0], **{f: (by_queue.get(k) or {}).get(f, 0) for f in ("open", "unassigned", "overdue")}}
              for k, v in QUEUES.items()]

    def count(sql: str) -> int:
        try:
            return fetch_one(sql)["c"]
        except Exception:
            return 0

    related = {
        "hires_unmatched": count("select count(*) as c from engagements where provider_id is null and status = 'open'"),
        "deals_to_follow_up": count(f"select count(*) as c from engagements e where {provider_service.follow_up_sql()}"),
        "wrong_info_reports": count("select count(*) as c from feedback_flags where status = 'open'"),
        "providers_pending": count("select count(*) as c from providers where status = 'pending'"),
        "org_submissions_pending": count(
            "select (select count(*) from organizations where status = 'pending') "
            "+ (select count(*) from org_service_revisions where status = 'pending') as c"
        ),
    }
    return {"totals": totals, "queues": queues, "related": related,
            "follow_up_hours": platform_settings.get_int("follow_up_hours")}


def purge_for_tests(ip: str) -> int:
    return execute("delete from support_tickets where ip = %s", (ip,))
