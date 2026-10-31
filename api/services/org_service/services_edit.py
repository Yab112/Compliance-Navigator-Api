"""The working copy of an organization's services: completeness, validation, saving and submitting."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from services.db import Jsonb, connection, fetch_all
from services import platform_settings
from .graph_sync import remove_service_from_graph
from .helpers import JSON_FIELDS, REQUIREMENT_FIELDS, SERVICE_FIELDS, OrgError, _log, _plain, _unique_slug, slugify


# ---------------------------------------------------------------- services (working copy)


SERVICE_LIST_COLUMNS = """
  s.id::text, s.org_id::text, s.slug, s.name, s.name_am, s.summary, s.status, s.version,
  s.published_at, s.updated_at, s.admin_note, (s.published_snapshot is not null) as is_live,
  s.last_confirmed_at, s.last_confirmed_by
"""


def _confirmation(last_confirmed_at: datetime | None, is_live: bool) -> dict:
    if not is_live:
        return {"confirmed_days_ago": None, "confirmation_due": False}
    if not last_confirmed_at:
        return {"confirmed_days_ago": None, "confirmation_due": True}
    days = (datetime.now(timezone.utc) - last_confirmed_at).days
    return {"confirmed_days_ago": days, "confirmation_due": days >= platform_settings.get_int("org_confirm_every_days")}


def list_org_services(org_id: str) -> list[dict]:
    rows = fetch_all(
        f"select {SERVICE_LIST_COLUMNS} from org_services s where s.org_id = %s order by s.created_at",
        (org_id,),
    )
    scheduled = {
        r["service_id"]: r for r in fetch_all(
            "select r.service_id::text, r.effective_at, r.change_summary from org_service_revisions r "
            "join org_services s on s.id = r.service_id where s.org_id = %s and r.status = 'scheduled'",
            (org_id,),
        )
    }
    scores = _completeness_by_service([org_id])
    for r in rows:
        r.update(_confirmation(r["last_confirmed_at"], r["is_live"]))
        r["completeness"] = scores[r["id"]]["completeness"] if r["id"] in scores else None
        sch = scheduled.get(r["id"])
        r["scheduled_change"] = {"effective_at": sch["effective_at"], "summary": sch["change_summary"]} if sch else None
    return _plain(rows)


def working_copy(service_id: str, org_id: str | None = None) -> dict | None:
    """The editable service with its requirements, questions and steps."""
    with connection() as conn:
        row = conn.execute(
            f"""
            select s.id::text, s.org_id::text, s.slug, {', '.join('s.' + f for f in SERVICE_FIELDS)},
                   s.status, s.admin_note, s.version, s.published_at, s.updated_at,
                   (s.published_snapshot is not null) as is_live, s.last_confirmed_at
            from org_services s where s.id = %s and (%s::uuid is null or s.org_id = %s::uuid)
            """,
            (service_id, org_id, org_id),
        ).fetchone()
        if not row:
            return None
        row["requirements"] = conn.execute(
            f"""
            select {', '.join(f for f in REQUIREMENT_FIELDS if f != 'issuing_service_id')},
                   issuing_service_id::text
            from org_service_requirements where service_id = %s order by position
            """,
            (service_id,),
        ).fetchall()
        row["questions"] = conn.execute(
            "select key, prompt, prompt_am, type, options, rules from org_service_questions "
            "where service_id = %s order by position",
            (service_id,),
        ).fetchall()
        row["steps"] = conn.execute(
            "select title, location, description, estimated_minutes from org_service_steps "
            "where service_id = %s order by position",
            (service_id,),
        ).fetchall()
        branch_count = conn.execute(
            "select count(*) as c from organization_branches where org_id = %s", (row["org_id"],)
        ).fetchone()["c"]
    row["branch_ids"] = [str(b) for b in row["branch_ids"] or []]
    row["renewal_service_id"] = str(row["renewal_service_id"]) if row["renewal_service_id"] else None
    row["org_branch_count"] = branch_count
    row["completeness"] = completeness(row)
    return _plain(row)


# ---------------------------------------------------------------- completeness

# Each check: (key, label, core?, test). Core fields are what a path step can't do without,
# so a service missing any of them can't be published.
def _has_fee(s: dict) -> bool:
    return bool(s.get("is_free") or s.get("fee_schedule") or s.get("fee_amount_min") is not None)


COMPLETENESS_CHECKS: list[tuple[str, str, bool, Any]] = [
    ("where", "Where people get it: at least one branch, or online only", True,
     lambda s: bool(s.get("branch_ids")) or s.get("delivery") == "online"),
    ("fee", "The fee, or that it is free", True, _has_fee),
    ("documents", "Documents to bring, or that none are needed", True,
     lambda s: bool(s.get("requirements")) or bool(s.get("no_documents_required"))),
    ("time", "How long it takes", True,
     lambda s: s.get("processing_minutes") is not None or bool((s.get("processing_time_text") or "").strip())),
    ("summary", "A short summary", False, lambda s: bool((s.get("summary") or "").strip())),
    ("who", "Who can apply", False, lambda s: bool((s.get("who_can_apply") or "").strip())),
    ("audience", "Who the service is for", False, lambda s: bool(s.get("audience"))),
    ("payment", "How to pay", False,
     lambda s: bool(s.get("is_free") or s.get("payment_methods") or (s.get("where_to_pay") or "").strip())),
    ("steps", "Steps at the office", False, lambda s: bool(s.get("steps")) or s.get("delivery") == "online"),
    ("windows", "Window or desk at each branch", False,
     lambda s: s.get("delivery") == "online" or (bool(s.get("branch_ids")) and all(
         any(d.get("branch_id") == bid and (d.get("window") or "").strip() for d in s.get("branch_details") or [])
         for bid in s.get("branch_ids") or []))),
    ("document_details", "Original or copy for every document", False,
     lambda s: bool(s.get("no_documents_required")) or (bool(s.get("requirements")) and all(
         r.get("original_or_copy") for r in s.get("requirements") or []))),
    ("proxy", "Whether someone can apply on the applicant's behalf", False, lambda s: s.get("proxy_allowed") is not None),
    ("outputs", "What the applicant receives", False, lambda s: bool(s.get("outputs"))),
    ("legal", "Legal basis", False, lambda s: bool((s.get("legal_basis") or "").strip())),
    ("contact", "A contact for questions", False,
     lambda s: bool(s.get("contact_phone") or s.get("contact_email"))),
    ("rejections", "Why applications get sent back", False, lambda s: bool(s.get("common_rejection_reasons"))),
    ("languages", "Languages served", False, lambda s: bool(s.get("languages"))),
]


def _completeness_by_service(org_ids: list[str]) -> dict[str, dict]:
    """Completeness of every service of these organizations in one query (no per-service loading).
    Maps service id to {org_id, archived, completeness}."""
    if not org_ids:
        return {}
    rows = fetch_all(
        f"""
        select s.id::text, s.org_id::text, (s.status = 'archived') as archived,
          {', '.join('s.' + f for f in SERVICE_FIELDS)},
          coalesce((select json_agg(json_build_object('original_or_copy', r.original_or_copy))
                    from org_service_requirements r where r.service_id = s.id), '[]'::json) as requirements,
          exists (select 1 from org_service_steps st where st.service_id = s.id) as has_steps
        from org_services s where s.org_id = any(%s::uuid[])
        """,
        (org_ids,),
    )
    out = {}
    for r in rows:
        r["branch_ids"] = [str(b) for b in r["branch_ids"] or []]
        r["steps"] = [{}] if r.pop("has_steps") else []
        out[r["id"]] = {"org_id": r["org_id"], "archived": r["archived"], "completeness": completeness(_plain(r))}
    return out


def completeness(service: dict) -> dict:
    done, missing, core_missing = 0, [], []
    for key, label, core, test in COMPLETENESS_CHECKS:
        try:
            ok = bool(test(service))
        except Exception:
            ok = False
        if ok:
            done += 1
        else:
            missing.append({"key": key, "label": label, "core": core})
            if core:
                core_missing.append(label)
    return {"score": round(100 * done / len(COMPLETENESS_CHECKS)), "missing": missing, "core_missing": core_missing}


# ---------------------------------------------------------------- saving


def _validate_service(conn, org_id: str, service_id: str | None, data: dict) -> None:
    keys = [r["key"] for r in data["requirements"]]
    if len(keys) != len(set(keys)):
        raise OrgError("Each requirement needs a unique key")
    qkeys = [q["key"] for q in data["questions"]]
    if len(qkeys) != len(set(qkeys)):
        raise OrgError("Each question needs a unique key")
    for q in data["questions"]:
        if q["type"] == "single_choice" and not q["options"]:
            raise OrgError(f"Question '{q['prompt']}' needs answer options")
        for rule in q["rules"]:
            unknown = set(rule["add_requirements"]) - set(keys)
            if unknown:
                raise OrgError(f"Question '{q['prompt']}' adds unknown requirements: {', '.join(sorted(unknown))}")
            if q["type"] == "number" and rule["op"] != "eq":
                try:
                    float(rule["value"])
                except ValueError:
                    raise OrgError(f"Question '{q['prompt']}' compares against a non-number") from None
    for r in data["requirements"]:
        issuer = r.get("issuing_service_id")
        if not issuer:
            continue
        if issuer == service_id:
            raise OrgError(f"'{r['name']}' can't require the service itself")
        other = conn.execute(
            "select org_id::text, published_snapshot is not null as live from org_services where id = %s",
            (issuer,),
        ).fetchone()
        if not other:
            raise OrgError(f"The service issuing '{r['name']}' was not found", 404)
        if other["org_id"] != org_id and not other["live"]:
            raise OrgError(f"The service issuing '{r['name']}' isn't published yet")
    if data["fee_amount_min"] is not None and data["fee_amount_max"] is not None \
            and data["fee_amount_max"] < data["fee_amount_min"]:
        raise OrgError("The maximum fee can't be lower than the minimum")
    for row in data.get("fee_schedule") or []:
        if row.get("amount_max") is not None and row["amount_max"] < row["amount_min"]:
            raise OrgError("In the fee schedule, a maximum can't be lower than its minimum")
    if data.get("is_free") and data.get("fee_schedule"):
        raise OrgError("A free service can't also have a fee schedule")
    branch_ids = set(data["branch_ids"]) | {d["branch_id"] for d in data.get("branch_details") or []}
    if branch_ids:
        found = conn.execute(
            "select count(*) as c from organization_branches where org_id = %s and id = any(%s::uuid[])",
            (org_id, list(branch_ids)),
        ).fetchone()["c"]
        if found != len(branch_ids):
            raise OrgError("Some branches don't belong to this organization")
    renewal = data.get("renewal_service_id")
    if renewal:
        if renewal == service_id:
            raise OrgError("A service can't be its own renewal; leave it empty if renewal is the same service")
        if not conn.execute("select 1 from org_services where id = %s", (renewal,)).fetchone():
            raise OrgError("The renewal service was not found", 404)


def _derive_fee_range(data: dict) -> None:
    """Keep the simple min/max (used for path totals and lists) in step with the schedule."""
    if data.get("is_free"):
        data["fee_amount_min"], data["fee_amount_max"] = 0, None
        return
    rows = [r for r in data.get("fee_schedule") or [] if r.get("currency", "ETB") == "ETB"] or data.get("fee_schedule") or []
    if rows:
        lows = [r["amount_min"] for r in rows]
        highs = [r["amount_max"] if r.get("amount_max") is not None else r["amount_min"] for r in rows]
        data["fee_amount_min"] = min(lows)
        data["fee_amount_max"] = max(highs) if max(highs) != min(lows) else None
        data["fee_currency"] = rows[0].get("currency", "ETB")


def save_service(org_id: str, service_id: str | None, data: dict, actor: str) -> dict:
    """Create or replace the working copy. A live service stays live until the next publish."""
    data = {**data}
    _derive_fee_range(data)
    with connection() as conn, conn.transaction():
        _validate_service(conn, org_id, service_id, data)
        values = [Jsonb(_plain(data.get(f))) if f in JSON_FIELDS else data.get(f) for f in SERVICE_FIELDS]
        if service_id is None:
            slug = _unique_slug(conn, "org_services", slugify(data["name"]), "and org_id = %s", (org_id,))
            service_id = conn.execute(
                f"insert into org_services (org_id, slug, {', '.join(SERVICE_FIELDS)}) "
                f"values (%s, %s, {', '.join(['%s'] * len(SERVICE_FIELDS))}) returning id::text",
                (org_id, slug, *values),
            ).fetchone()["id"]
            _log(conn, "service_created", org_id=org_id, service_id=service_id, actor=actor)
        else:
            current = conn.execute(
                "select status from org_services where id = %s and org_id = %s for update", (service_id, org_id)
            ).fetchone()
            if not current:
                raise OrgError("Service not found", 404)
            sets = ", ".join(f"{f} = %s" for f in SERVICE_FIELDS)
            # A scheduled change keeps waiting for its date; editing again replaces it on resubmit
            conn.execute(
                f"update org_services set {sets}, status = 'draft', updated_at = now() where id = %s",
                (*values, service_id),
            )
            # Any waiting submission no longer matches what's being edited
            conn.execute(
                "update org_service_revisions set status = 'superseded' where service_id = %s and status = 'pending'",
                (service_id,),
            )
            for table in ("org_service_requirements", "org_service_questions", "org_service_steps"):
                conn.execute(f"delete from {table} where service_id = %s", (service_id,))
            _log(conn, "service_edited", org_id=org_id, service_id=service_id, actor=actor)

        for i, r in enumerate(data["requirements"]):
            cols = ["service_id", "position", *REQUIREMENT_FIELDS]
            conn.execute(
                f"insert into org_service_requirements ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
                (service_id, i, *[r.get(f) if f != "alternatives" else (r.get(f) or []) for f in REQUIREMENT_FIELDS]),
            )
        for i, q in enumerate(data["questions"]):
            conn.execute(
                """
                insert into org_service_questions (service_id, position, key, prompt, prompt_am, type, options, rules)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (service_id, i, q["key"], q["prompt"], q.get("prompt_am"), q["type"], Jsonb(q["options"]),
                 Jsonb(q["rules"])),
            )
        for i, st in enumerate(data["steps"]):
            conn.execute(
                """
                insert into org_service_steps (service_id, position, title, location, description, estimated_minutes)
                values (%s, %s, %s, %s, %s, %s)
                """,
                (service_id, i, st["title"], st.get("location"), st.get("description"), st.get("estimated_minutes")),
            )
    return working_copy(service_id, org_id)


def submit_service(org_id: str, service_id: str, actor: str, change: dict | None = None) -> dict:
    """Freeze the working copy for review. Changes to a live service say what, why and from when."""
    service = working_copy(service_id, org_id)
    change = change or {}
    if not service:
        raise OrgError("Service not found", 404)
    if service["status"] == "submitted":
        raise OrgError("This service is already waiting for review", 409)
    if service["status"] in ("published", "scheduled"):
        raise OrgError("Nothing changed since the last approval", 409)
    if not (service.get("summary") or "").strip():
        raise OrgError("Add a short summary before submitting")
    if service["is_live"] and not (change.get("change_summary") or "").strip():
        raise OrgError("Tell us what changed, so people following this service can be told")
    effective = change.get("effective_at")
    if effective and isinstance(effective, str):
        effective = date.fromisoformat(effective)
    if effective and effective < date.today():
        raise OrgError("The effective date can't be in the past")
    snapshot = _snapshot(service)
    with connection() as conn, conn.transaction():
        conn.execute(
            "update org_service_revisions set status = 'superseded' where service_id = %s and status = 'pending'",
            (service_id,),
        )
        conn.execute(
            """
            insert into org_service_revisions (service_id, snapshot, submitted_by, change_summary, change_reason,
              effective_at)
            values (%s, %s, %s, %s, %s, %s)
            """,
            (service_id, Jsonb(snapshot), actor, change.get("change_summary"), change.get("change_reason"), effective),
        )
        conn.execute(
            "update org_services set status = 'submitted', admin_note = null, updated_at = now() where id = %s",
            (service_id,),
        )
        _log(conn, "service_submitted", org_id=org_id, service_id=service_id, actor=actor,
             note=change.get("change_summary"))
    return working_copy(service_id, org_id)


def archive_service(org_id: str, service_id: str, actor: str) -> dict:
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "update org_services set status = 'archived', updated_at = now() where id = %s and org_id = %s returning id",
            (service_id, org_id),
        ).fetchone()
        if not row:
            raise OrgError("Service not found", 404)
        conn.execute(
            "update org_service_revisions set status = 'superseded' where service_id = %s "
            "and status in ('pending', 'scheduled')",
            (service_id,),
        )
        _log(conn, "service_archived", org_id=org_id, service_id=service_id, actor=actor)
        remove_service_from_graph(service_id, conn)
    return working_copy(service_id, org_id)


SNAPSHOT_KEYS = ("id", "org_id", "slug", *SERVICE_FIELDS, "requirements", "questions", "steps")


def _snapshot(service: dict) -> dict:
    return _plain({k: service.get(k) for k in SNAPSHOT_KEYS})
