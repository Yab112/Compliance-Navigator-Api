"""In-app notifications: short messages shown under the bell in the header."""

from __future__ import annotations

from services.db import execute, fetch_all, fetch_one

COLUMNS = "id::text, kind, title, body, link, created_at, read_at"


def notify(user_ids: list[str], *, kind: str, title: str, body: str | None = None, link: str | None = None) -> int:
    ids = sorted({u for u in user_ids if u})
    if not ids:
        return 0
    execute(
        """
        insert into notifications (user_id, kind, title, body, link)
        select u, %s, %s, %s, %s from unnest(%s::uuid[]) as u
        """,
        (kind, title, body, link, ids),
    )
    return len(ids)


def list_for(user_id: str, limit: int = 30) -> dict:
    items = fetch_all(
        f"select {COLUMNS} from notifications where user_id = %s order by created_at desc limit %s",
        (user_id, limit),
    )
    unread = fetch_one(
        "select count(*) as c from notifications where user_id = %s and read_at is null", (user_id,)
    )["c"]
    return {"items": items, "unread": unread}


def mark_read(user_id: str, ids: list[str] | None) -> int:
    rows = fetch_all(
        """
        update notifications set read_at = now()
        where user_id = %s and read_at is null and (%s::uuid[] is null or id = any(%s::uuid[]))
        returning id
        """,
        (user_id, ids, ids),
    )
    return len(rows)


def roadmap_owners_for_documents(document_ids: list[str]) -> list[str]:
    """Users with a saved path that has a step for any of these documents."""
    if not document_ids:
        return []
    rows = fetch_all(
        """
        select distinct r.user_id::text from roadmaps r
        where r.user_id is not null and exists (
          select 1 from jsonb_array_elements(r.snapshot_json->'steps') st where st->>'id' = any(%s)
        )
        """,
        (document_ids,),
    )
    return [r["user_id"] for r in rows]
