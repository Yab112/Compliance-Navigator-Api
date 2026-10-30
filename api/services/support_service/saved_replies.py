"""Saved replies staff reuse, with placeholders filled from the ticket."""

from __future__ import annotations

import re

from psycopg import errors as pg_errors
from services.db import execute, fetch_all, fetch_one
from .common import QUEUES, SupportError, _is_uuid, _like, get, queue_label


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
