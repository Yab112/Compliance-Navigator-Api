"""Persist roadmaps and references in Supabase Postgres."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from services.supabase_client import get_supabase, is_supabase_configured


def _auth_user_id(user: Any) -> str | None:
    if user is None:
        return None
    uid = getattr(user, "id", None)
    if uid is None:
        return None
    return str(uid)


def save_roadmap_to_supabase(roadmap: dict, user: Any = None) -> bool:
    if not is_supabase_configured():
        return False

    sb = get_supabase()
    req = roadmap.get("request", {})
    row = {
        "id": roadmap["id"],
        "user_id": _auth_user_id(user),
        "goal": req.get("goal"),
        "sub_city": req.get("subCity"),
        "industry": req.get("industry"),
        "documents_held": req.get("documentsHeld", []),
        "tracked_completed": roadmap.get("trackedCompleted", []),
        "snapshot_json": roadmap,
    }
    sb.table("roadmaps").upsert(row).execute()
    return True


def get_roadmap_from_supabase(roadmap_id: str) -> dict | None:
    if not is_supabase_configured():
        return None

    sb = get_supabase()
    result = (
        sb.table("roadmaps")
        .select("snapshot_json")
        .eq("id", roadmap_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    snap = result.data[0].get("snapshot_json")
    if isinstance(snap, dict):
        return snap
    if isinstance(snap, str):
        return json.loads(snap)
    return None


def update_roadmap_in_supabase(roadmap: dict) -> bool:
    return save_roadmap_to_supabase(roadmap)


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
) -> bool:
    if not is_supabase_configured():
        return False

    sb = get_supabase()
    sb.table("manual_references").upsert({
        "id": ref_id,
        "user_id": user_id,
        "title": title,
        "service_id": service_id,
        "company_name": company_name,
        "file_path": file_path,
        "mime_type": mime_type,
        "raw_text": raw_text,
        "extraction_status": extraction_status,
    }).execute()
    return True


def upsert_profile(email: str, fullname: str, profile_id: str | UUID) -> bool:
    if not is_supabase_configured():
        return False

    sb = get_supabase()
    sb.table("profiles").upsert({
        "id": str(profile_id),
        "email": email,
        "fullname": fullname,
    }).execute()
    return True
