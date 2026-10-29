"""'This is wrong' flags from users, reviewed in the admin queue."""

from __future__ import annotations

from services.db import fetch_all, fetch_one

COLUMNS = """
  f.id::text, f.user_id::text, u.email as user_email, f.target_type, f.target_id,
  f.message, f.status, f.resolution_note, f.resolved_by, f.created_at, f.resolved_at
"""


def create_flag(target_type: str, target_id: str | None, message: str, user_id: str | None) -> dict:
    # Reports about an organization's own service also land in that organization's inbox
    org_id = None
    if target_type == "org_service" and target_id:
        org = fetch_one("select org_id::text from org_services where id::text = %s", (target_id,))
        org_id = org["org_id"] if org else None
    row = fetch_one(
        "insert into feedback_flags (user_id, target_type, target_id, message, org_id) "
        "values (%s, %s, %s, %s, %s) returning id::text",
        (user_id, target_type, target_id, message, org_id),
    )
    return get_flag(row["id"])


def get_flag(flag_id: str) -> dict | None:
    return fetch_one(
        f"select {COLUMNS} from feedback_flags f left join users u on u.id = f.user_id "
        "where f.id::text = %s",
        (flag_id,),
    )


def list_flags(status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    return fetch_all(
        f"select {COLUMNS} from feedback_flags f left join users u on u.id = f.user_id "
        "where %(status)s::text is null or f.status = %(status)s "
        "order by f.created_at desc limit %(limit)s offset %(offset)s",
        {"status": status, "limit": limit, "offset": offset},
    )


def count_flags(status: str | None = None) -> int:
    return fetch_one("select count(*) as c from feedback_flags where %(status)s::text is null or status = %(status)s",
                     {"status": status})["c"]


def resolve_flag(flag_id: str, status: str, note: str | None, actor: str) -> dict | None:
    row = fetch_one(
        "update feedback_flags set status = %s, resolution_note = %s, resolved_by = %s, "
        "resolved_at = now() where id::text = %s returning id::text",
        (status, note, actor, flag_id),
    )
    return get_flag(row["id"]) if row else None
