"""The staff side: the ticket list and export, replies, and ticket updates."""

from __future__ import annotations

from services import notifications
from services.db import connection, fetch_all, fetch_one
from .common import (
    OVERDUE_SQL,
    PRIORITIES,
    PRIORITY_ORDER,
    QUEUES,
    SLA_HOURS,
    STATUS_LABELS,
    TICKET_FROM,
    TICKET_SELECT,
    SupportError,
    _add_message,
    _is_uuid,
    _like,
    _shape,
    get,
    log_staff_action,
    messages,
    queue_label,
)


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
