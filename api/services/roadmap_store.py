"""Persist roadmaps and manual references in Postgres."""

from __future__ import annotations

from typing import Any

from services.db import fetch_all, Jsonb, execute, fetch_one


def _auth_user_id(user: Any) -> str | None:
    uid = getattr(user, "id", None) if user is not None else None
    return str(uid) if uid is not None else None


def save_roadmap(roadmap: dict, user: Any = None) -> None:
    req = roadmap.get("request", {})
    execute(
        """
        insert into roadmaps (id, user_id, goal, sub_city, industry, documents_held,
                              tracked_completed, snapshot_json)
        values (%(id)s, %(user_id)s, %(goal)s, %(sub_city)s, %(industry)s,
                %(documents_held)s, %(tracked_completed)s, %(snapshot)s)
        on conflict (id) do update set
          user_id = coalesce(excluded.user_id, roadmaps.user_id),
          documents_held = excluded.documents_held,
          tracked_completed = excluded.tracked_completed,
          snapshot_json = excluded.snapshot_json,
          updated_at = now()
        """,
        {
            "id": roadmap["id"],
            "user_id": _auth_user_id(user),
            "goal": req.get("goal"),
            "sub_city": req.get("subCity"),
            "industry": req.get("industry"),
            "documents_held": req.get("documentsHeld", []),
            "tracked_completed": roadmap.get("trackedCompleted", []),
            "snapshot": Jsonb(roadmap),
        },
    )


def get_roadmap(roadmap_id: str) -> dict | None:
    row = fetch_one("select snapshot_json from roadmaps where id::text = %s", (roadmap_id,))
    return row["snapshot_json"] if row else None


def save_manual_reference(
    *,
    ref_id: str,
    title: str,
    service_id: str | None,
    company_name: str | None,
    file_path: str | None,
    mime_type: str | None,
    raw_text: str | None,
    extraction_status: str,
    user_id: str | None = None,
    institution_id: str | None = None,
) -> None:
    execute(
        """
        insert into manual_references (id, user_id, title, service_id, company_name,
          institution_id, file_path, mime_type, raw_text, extraction_status)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (id) do nothing
        """,
        (ref_id, user_id, title, service_id, company_name, institution_id,
         file_path, mime_type, raw_text, extraction_status),
    )


def owner_of(roadmap_id: str) -> tuple[bool, str | None]:
    """(exists, owner user id)."""
    try:
        row = fetch_one("select user_id::text from roadmaps where id::text = %s", (roadmap_id,))
    except Exception:
        return False, None
    return (True, row["user_id"]) if row else (False, None)


def claim(roadmap_id: str, user_id: str) -> bool:
    """Save a path to an account. A path someone else saved is never taken over."""
    return execute(
        "update roadmaps set user_id = %s, updated_at = now() where id::text = %s and (user_id is null or user_id = %s)",
        (user_id, roadmap_id, user_id),
    ) > 0


def remove(roadmap_id: str, user_id: str) -> bool:
    return execute("delete from roadmaps where id::text = %s and user_id = %s", (roadmap_id, user_id)) > 0


def count_for_user(user_id: str) -> int:
    return fetch_one("select count(*) as c from roadmaps where user_id = %s", (user_id,))["c"]


def list_for_user(user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    rows = fetch_all(
        """
        select id::text, goal, sub_city, tracked_completed, snapshot_json->'request' as request,
               jsonb_array_length(coalesce(snapshot_json->'steps', '[]'::jsonb)) as step_count,
               created_at, updated_at
        from roadmaps where user_id = %s order by updated_at desc limit %s offset %s
        """,
        (user_id, limit, offset),
    )
    out = []
    for r in rows:
        req = r["request"] or {}
        out.append({
            "id": r["id"], "goal": r["goal"], "goalLabel": req.get("goalLabel") or (r["goal"] or "").replace("_", " ").capitalize(),
            "subCity": r["sub_city"], "subCityLabel": req.get("subCityLabel") or r["sub_city"],
            "category": req.get("category"), "steps": r["step_count"], "completed": len(r["tracked_completed"] or []),
            "createdAt": r["created_at"].isoformat(), "updatedAt": r["updated_at"].isoformat(),
        })
    return out


def get_feedback(roadmap_id: str) -> dict | None:
    return fetch_one(
        "select accuracy, days_taken, steps_different, what_was_different, would_recommend, comment, created_at "
        "from path_feedback where roadmap_id::text = %s",
        (roadmap_id,),
    )


def save_feedback(roadmap: dict, user_id: str | None, data: dict) -> dict:
    """One feedback per path. Steps that were different are flagged for the data team."""
    from services import feedback_service

    step_titles = {s["id"]: s.get("title") or s["id"] for s in roadmap.get("steps", [])}
    different = [s for s in data.get("steps_different") or [] if s in step_titles]
    execute(
        """
        insert into path_feedback (roadmap_id, user_id, goal, accuracy, days_taken, steps_different,
          what_was_different, would_recommend, comment)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (roadmap_id) do nothing
        """,
        (roadmap["id"], user_id, (roadmap.get("request") or {}).get("goal"), data["accuracy"], data.get("days_taken"),
         different, data.get("what_was_different"), data.get("would_recommend"), data.get("comment")),
    )
    note = (data.get("what_was_different") or "").strip()
    for step_id in different:
        feedback_service.create_flag(
            "document", step_id,
            f"Finished a {(roadmap.get('request') or {}).get('goalLabel') or 'path'}: the step "
            f"\"{step_titles[step_id]}\" was different from what we showed. {note}".strip()[:2000],
            user_id,
        )
    return get_feedback(roadmap["id"])
