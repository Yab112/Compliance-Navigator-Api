"""Support desk: requests from the assistant's handoff, the contact form and reports, worked by staff.

A ticket belongs to one queue (the team that answers it). Staff replies notify the customer and,
when the ticket came from the chat, appear in that chat conversation as a `staff` message.
"""

from __future__ import annotations

import os
import re

from services import notifications
from services.db import Jsonb, connection, execute, fetch_all, fetch_one

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
TICKETS_PER_IP_PER_HOUR = 10

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


TICKET_SELECT = """
select t.id::text, t.ref, t.subject, t.queue, t.status, t.priority, t.source, t.category,
       t.contact_name, t.contact_phone, t.contact_email, t.user_id::text, u.email as user_email,
       t.conversation_id::text, t.service_key, t.service_title, t.context,
       t.assignee_id::text, nullif(a.fullname, '') as assignee_name, a.email as assignee_email,
       t.created_at, t.updated_at, t.first_response_at, t.resolved_at, t.sla_due_at,
       (t.status in ('new', 'open') and t.first_response_at is null and t.sla_due_at < now()) as overdue,
       lm.body as last_message_preview, lm.created_at as last_message_at,
       coalesce(lm.author_kind = 'customer', true) as awaiting_staff,
       (select count(*) from support_messages m where m.ticket_id = t.id and not m.internal) as message_count
from support_tickets t
left join users u on u.id = t.user_id
left join users a on a.id = t.assignee_id
left join lateral (
  select body, created_at, author_kind from support_messages m
  where m.ticket_id = t.id and not m.internal and m.author_kind in ('customer', 'staff')
  order by m.id desc limit 1
) lm on true
"""


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
    return row


def get(ticket_id: str) -> dict | None:
    try:
        return _shape(fetch_one(f"{TICKET_SELECT} where t.id = %s", (ticket_id,)))
    except Exception:  # malformed id
        return None


def messages(ticket_id: str, *, include_internal: bool) -> list[dict]:
    internal = "" if include_internal else "and not m.internal"
    return fetch_all(
        f"""
        select m.id, m.author_kind, coalesce(nullif(u.fullname, ''), u.email) as author_name, m.body, m.internal, m.created_at
        from support_messages m left join users u on u.id = m.author_id
        where m.ticket_id = %s {internal} order by m.id
        """,
        (ticket_id,),
    )


def _add_message(conn, ticket_id: str, kind: str, body: str, author_id: str | None = None, internal: bool = False):
    conn.execute(
        "insert into support_messages (ticket_id, author_kind, author_id, body, internal) values (%s, %s, %s, %s, %s)",
        (ticket_id, kind, author_id, body, internal),
    )


# ---------------------------------------------------------------- customers


def create_ticket(
    *, subject: str, body: str, queue: str = "customer_support", priority: str | None = None,
    source: str = "contact_form", user_id: str | None = None, name: str | None = None, phone: str | None = None,
    email: str | None = None, conversation_id: str | None = None, service_key: str | None = None,
    service_title: str | None = None, context: dict | None = None, category: str | None = None, ip: str | None = None,
) -> dict:
    if queue not in QUEUES:
        raise SupportError("Unknown team")
    subject, body = (subject or "").strip(), (body or "").strip()
    if not subject or not body:
        raise SupportError("Tell us what you need help with")
    if not user_id and not (name and (phone or email)):
        raise SupportError("Leave your name and a phone number or email so we can reach you")
    if ip:
        recent = fetch_one(
            "select count(*) as c from support_tickets where ip = %s and created_at > now() - interval '1 hour'", (ip,)
        )["c"]
        if recent >= TICKETS_PER_IP_PER_HOUR:
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
              priority, source, conversation_id, service_key, service_title, context, ip, sla_due_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now() + make_interval(hours => %s))
            returning id::text
            """,
            (user_id, name, phone, email, queue, category, subject[:200], priority, source, conversation_id,
             service_key, service_title, Jsonb(context or {}), ip, SLA_HOURS[priority]),
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
    body = (body or "").strip()
    if not body:
        raise SupportError("Write a message first")
    with connection() as conn, conn.transaction():
        _add_message(conn, ticket_id, "customer", body[:4000], user_id)
        conn.execute(
            """
            update support_tickets set updated_at = now(), resolved_at = null,
              status = case when status = 'new' then 'new' else 'open' end
            where id = %s
            """,
            (ticket_id,),
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
    return fetch_all(
        "select id::text, coalesce(nullif(fullname, ''), email) as name from users "
        "where role = 'admin' and is_active order by 2"
    )


def admin_list(*, queue: str | None = None, status: str | None = "active", assigned: str | None = None,
               priority: str | None = None, q: str | None = None, staff_id: str | None = None,
               limit: int = 25, offset: int = 0) -> dict:
    where, params = ["true"], {}
    if queue:
        where.append("t.queue = %(queue)s")
        params["queue"] = queue
    if status == "active" or not status:
        where.append("t.status in ('new', 'open', 'waiting_customer')")
    elif status == "overdue":
        where.append("t.status in ('new', 'open') and t.first_response_at is null and t.sla_due_at < now()")
    elif status != "all":
        where.append("t.status = %(status)s")
        params["status"] = status
    if assigned == "me" and staff_id:
        where.append("t.assignee_id = %(me)s")
        params["me"] = staff_id
    elif assigned == "none":
        where.append("t.assignee_id is null")
    if priority:
        where.append("t.priority = %(priority)s")
        params["priority"] = priority
    if q:
        where.append(
            "(t.ref ilike %(q)s or t.subject ilike %(q)s or t.contact_name ilike %(q)s or t.contact_phone ilike %(q)s "
            "or t.contact_email ilike %(q)s or u.email ilike %(q)s)"
        )
        params["q"] = f"%{q.strip()}%"
    clause = " and ".join(where)
    total = fetch_one(
        f"select count(*) as c from support_tickets t left join users u on u.id = t.user_id where {clause}", params
    )["c"]
    rows = fetch_all(
        f"""{TICKET_SELECT} where {clause}
        order by (t.status in ('new', 'open') and t.first_response_at is null and t.sla_due_at < now()) desc,
                 {PRIORITY_ORDER}, t.created_at
        limit %(limit)s offset %(offset)s""",
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": [_shape(r) for r in rows]}


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


def staff_reply(ticket_id: str, *, author: dict, body: str, internal: bool = False) -> dict:
    """author: {id, name}"""
    from assistant import store

    ticket = get(ticket_id)
    if not ticket:
        raise SupportError("Request not found", 404)
    body = (body or "").strip()
    if not body:
        raise SupportError("Write a message first")
    with connection() as conn, conn.transaction():
        _add_message(conn, ticket_id, "staff", body[:4000], author["id"], internal)
        if not internal:
            conn.execute(
                """
                update support_tickets set updated_at = now(), first_response_at = coalesce(first_response_at, now()),
                  status = case when status in ('resolved', 'closed') then status else 'waiting_customer' end,
                  assignee_id = coalesce(assignee_id, %s)
                where id = %s
                """,
                (author["id"], ticket_id),
            )
        else:
            conn.execute("update support_tickets set updated_at = now() where id = %s", (ticket_id,))
    if not internal:
        team = ticket["queue_label"]
        if ticket["conversation_id"]:
            store.add_message(ticket["conversation_id"], "staff", body,
                              {"staff": {"name": author["name"], "team": team}, "ticket": ticket["ref"]})
        if ticket["user_id"]:
            notifications.notify([ticket["user_id"]], kind="support_reply", title=f"{team} replied to {ticket['ref']}",
                                 body=body[:140], link=f"/account/support/{ticket_id}")
    return admin_detail(ticket_id)


def update(ticket_id: str, data: dict, *, author: dict) -> dict:
    ticket = get(ticket_id)
    if not ticket:
        raise SupportError("Request not found", 404)
    sets, params, notes = [], [], []
    if data.get("status") and data["status"] != ticket["status"]:
        if data["status"] not in STATUS_LABELS:
            raise SupportError("Unknown status")
        sets.append("status = %s")
        params.append(data["status"])
        sets.append("resolved_at = " + ("now()" if data["status"] in ("resolved", "closed") else "null"))
        notes.append(f"Status changed to {STATUS_LABELS[data['status']].lower()}")
    if data.get("priority") and data["priority"] != ticket["priority"]:
        if data["priority"] not in PRIORITIES:
            raise SupportError("Unknown priority")
        sets += ["priority = %s", "sla_due_at = created_at + make_interval(hours => %s)"]
        params += [data["priority"], SLA_HOURS[data["priority"]]]
        notes.append(f"Priority set to {data['priority']}")
    if data.get("queue") and data["queue"] != ticket["queue"]:
        if data["queue"] not in QUEUES:
            raise SupportError("Unknown team")
        sets.append("queue = %s")
        params.append(data["queue"])
        notes.append(f"Moved to {queue_label(data['queue'])}")
    if "assignee_id" in data and data["assignee_id"] != ticket["assignee_id"]:
        if data["assignee_id"] and not any(s["id"] == data["assignee_id"] for s in staff()):
            raise SupportError("Can only assign to staff")
        sets.append("assignee_id = %s")
        params.append(data["assignee_id"])
        name = next((s["name"] for s in staff() if s["id"] == data["assignee_id"]), None)
        notes.append(f"Assigned to {name}" if name else "Unassigned")
    if sets:
        if ticket["status"] == "new" and "status = %s" not in sets:
            sets.append("status = 'open'")
        with connection() as conn, conn.transaction():
            conn.execute(f"update support_tickets set {', '.join(sets)}, updated_at = now() where id = %s",
                         (*params, ticket_id))
            _add_message(conn, ticket_id, "system", f"{'. '.join(notes)} by {author['name']}.", author["id"], True)
        if data.get("status") == "resolved" and ticket["user_id"]:
            notifications.notify([ticket["user_id"]], kind="support_resolved", title=f"{ticket['ref']} was resolved",
                                 body=ticket["subject"], link=f"/account/support/{ticket_id}")
    return admin_detail(ticket_id)


def summary(staff_id: str | None) -> dict:
    totals = fetch_one(
        """
        select count(*) filter (where status = 'new') as new,
               count(*) filter (where status = 'open') as open,
               count(*) filter (where status = 'waiting_customer') as waiting_customer,
               count(*) filter (where status in ('new', 'open') and first_response_at is null and sla_due_at < now()) as overdue,
               count(*) filter (where status in ('new', 'open', 'waiting_customer') and assignee_id is null) as unassigned,
               count(*) filter (where status in ('new', 'open', 'waiting_customer') and assignee_id = %s) as mine,
               count(*) filter (where status in ('resolved', 'closed') and resolved_at > now() - interval '7 days') as resolved_7d,
               round(avg(extract(epoch from first_response_at - created_at) / 60)
                     filter (where first_response_at > now() - interval '30 days'))::int as avg_first_response_minutes
        from support_tickets
        """,
        (staff_id,),
    )
    by_queue = {
        r["queue"]: r for r in fetch_all(
            """
            select queue, count(*) filter (where status in ('new', 'open', 'waiting_customer')) as open,
                   count(*) filter (where status in ('new', 'open', 'waiting_customer') and assignee_id is null) as unassigned,
                   count(*) filter (where status in ('new', 'open') and first_response_at is null and sla_due_at < now()) as overdue
            from support_tickets group by queue
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
        "deals_to_follow_up": count(
            "select count(*) as c from engagements e where e.status = 'completed' and e.client_confirmed_at is null "
            "and e.payment_status <> 'paid' and coalesce(e.completed_at, e.updated_at) < now() - interval '48 hours'"
        ),
        "wrong_info_reports": count("select count(*) as c from feedback_flags where status = 'open'"),
        "providers_pending": count("select count(*) as c from providers where status = 'pending'"),
        "org_submissions_pending": count(
            "select (select count(*) from organizations where status = 'pending') "
            "+ (select count(*) from org_service_revisions where status = 'pending') as c"
        ),
    }
    return {"totals": totals, "queues": queues, "related": related}


def purge_for_tests(ip: str) -> int:
    return execute("delete from support_tickets where ip = %s", (ip,))
