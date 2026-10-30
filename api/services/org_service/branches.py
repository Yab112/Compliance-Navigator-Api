"""Branches (offices) of an organization."""

from __future__ import annotations

from services.db import Jsonb, connection, execute, fetch_all, fetch_one
from .helpers import OrgError


# ---------------------------------------------------------------- branches

BRANCH_FIELDS = ("name", "region", "sub_city", "woreda", "address", "latitude", "longitude", "map_url", "phone", "hours",
                 "landmark", "email", "hours_schedule")
DAY_LABEL = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}


def hours_text(schedule: list[dict] | None) -> str | None:
    """'Mon to Fri 08:30 to 17:30 (lunch 12:30 to 13:30) · Sat 08:30 to 12:30' from the weekly grid."""
    if not schedule:
        return None
    groups: list[tuple[list[str], str]] = []
    for d in schedule:
        if d.get("closed") or not d.get("open") or not d.get("close"):
            continue
        label = f"{d['open']} to {d['close']}"
        if d.get("lunch_start") and d.get("lunch_end"):
            label += f" (lunch {d['lunch_start']} to {d['lunch_end']})"
        if groups and groups[-1][1] == label:
            groups[-1][0].append(d["day"])
        else:
            groups.append(([d["day"]], label))
    parts = []
    for days, label in groups:
        span = DAY_LABEL[days[0]] if len(days) == 1 else f"{DAY_LABEL[days[0]]} to {DAY_LABEL[days[-1]]}"
        parts.append(f"{span} {label}")
    return " · ".join(parts) or None


def _branch_values(b: dict) -> dict:
    vals = {k: b.get(k) for k in BRANCH_FIELDS}
    vals["hours_schedule"] = Jsonb(b.get("hours_schedule") or [])
    # Free-text hours stay in sync with the grid so older readers still show something
    if b.get("hours_schedule") and not (b.get("hours") or "").strip():
        vals["hours"] = hours_text(b["hours_schedule"])
    return vals


def _insert_branch(conn, org_id: str, b: dict) -> dict:
    vals = _branch_values(b)
    return conn.execute(
        f"insert into organization_branches (org_id, {', '.join(vals)}) values (%s, {', '.join(['%s'] * len(vals))}) "
        "returning id::text",
        (org_id, *vals.values()),
    ).fetchone()


def list_branches(org_id: str) -> list[dict]:
    return fetch_all(
        f"select id::text, {', '.join(BRANCH_FIELDS)} from organization_branches where org_id = %s order by created_at",
        (org_id,),
    )


def add_branch(org_id: str, b: dict) -> list[dict]:
    with connection() as conn:
        _insert_branch(conn, org_id, b)
    return list_branches(org_id)


def update_branch(org_id: str, branch_id: str, b: dict) -> list[dict]:
    vals = _branch_values(b)
    sets = ", ".join(f"{k} = %s" for k in vals)
    row = fetch_one(
        f"update organization_branches set {sets} where id = %s and org_id = %s returning id",
        (*vals.values(), branch_id, org_id),
    )
    if not row:
        raise OrgError("Branch not found", 404)
    return list_branches(org_id)


def delete_branch(org_id: str, branch_id: str) -> list[dict]:
    execute("delete from organization_branches where id = %s and org_id = %s", (branch_id, org_id))
    execute("update org_services set branch_ids = array_remove(branch_ids, %s::uuid) where org_id = %s",
            (branch_id, org_id))
    execute(
        "update org_services set branch_details = coalesce((select jsonb_agg(d) from jsonb_array_elements(branch_details) d "
        "where d->>'branch_id' <> %s), '[]') where org_id = %s",
        (branch_id, org_id),
    )
    return list_branches(org_id)
