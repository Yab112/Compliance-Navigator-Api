"""Organization onboarding: organizations describe the services they give.

Each org_services row (plus its requirement, question and step rows) is the working
copy the organization edits. Submitting freezes it into a revision; publishing copies
that revision into published_snapshot, which is all the public ever sees, and syncs
the knowledge graph. Requirements that point at another organization's service are
what connect organizations into cross-organization paths.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from services import catalog_service
from services.db import Jsonb, connection, execute, fetch_all, fetch_one

log = logging.getLogger(__name__)

ORG_ACTIONS = {  # draft registrations aren't reviewable until the organization sends them
    "verify": ({"pending", "rejected"}, "verified"),
    "reject": ({"pending"}, "rejected"),
    "suspend": ({"verified"}, "suspended"),
    "reinstate": ({"suspended"}, "verified"),
}
NOTE_REQUIRED = {"reject", "suspend", "request_changes"}
# Changing these on a verified organization sends it back for review
IDENTITY_FIELDS = {"name", "org_type"}
ORG_EDITABLE = (
    "name", "name_am", "org_type", "sector", "description", "website", "phone", "email",
    "hq_address", "region", "sub_city", "representative_name", "representative_title", "official_email",
    "steward_name", "steward_role", "steward_phone", "steward_email", "onboarding_step",
)
SERVICE_FIELDS = (
    "name", "name_am", "summary", "who_can_apply", "delivery", "online_url", "fee_amount_min",
    "fee_amount_max", "fee_currency", "fee_notes", "payment_methods", "processing_time_text",
    "processing_minutes", "legal_basis", "forms", "common_rejection_reasons", "faq", "branch_ids",
    "outputs", "fee_schedule", "is_free", "where_to_pay", "no_documents_required",
    "appointment_required", "appointment_how", "appointment_url", "appointment_phone", "proxy_allowed",
    "proxy_notes", "online_parts", "languages", "accessibility_notes", "audience", "legal_reference_number",
    "legal_effective_date", "contact_name", "contact_phone", "contact_email", "output_validity_months",
    "renewal_service_id", "late_renewal_penalty", "branch_details",
)
JSON_FIELDS = {"forms", "faq", "outputs", "fee_schedule", "branch_details"}
REQUIREMENT_FIELDS = (
    "key", "kind", "name", "document_id", "issuing_service_id", "required", "notes", "original_or_copy",
    "copies", "notarized", "translated", "max_age_days", "photo_specs", "applies_to", "alternatives",
)
# An organization confirms each live service is still accurate at least this often
CONFIRM_EVERY_DAYS = 90

PUBLIC_ORG_COLUMNS = """
  o.id::text, o.slug, o.name, o.name_am, o.org_type, o.sector, o.description, o.logo_url,
  o.website, o.phone, o.email, o.hq_address, o.region, o.sub_city, o.catalog_institution_id,
  o.status, o.created_at
"""
MEMBER_ORG_COLUMNS = PUBLIC_ORG_COLUMNS + """,
  o.representative_name, o.representative_title, o.official_email,
  (o.authorization_letter_key is not null) as has_authorization_letter,
  o.verification_note, o.reviewed_at, o.updated_at, o.onboarding_step, o.submitted_at,
  o.steward_name, o.steward_role, o.steward_phone, o.steward_email, o.data_commitment_at
"""
ADMIN_ORG_COLUMNS = MEMBER_ORG_COLUMNS + """,
  o.authorization_letter_key, o.reviewed_by,
  (select email from users u where u.id = o.created_by) as created_by_email
"""


class OrgError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------- helpers


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:60] or "org"


def _unique_slug(conn, table: str, base: str, scope_sql: str = "", scope_params: tuple = ()) -> str:
    slug, n = base, 2
    while conn.execute(
        f"select 1 from {table} where slug = %s {scope_sql}", (slug, *scope_params)
    ).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _plain(value: Any) -> Any:
    """JSON-safe copy of DB values (Decimal, datetime, UUID)."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is not None and type(value).__name__ == "UUID":
        return str(value)
    return value


def _log(conn, action: str, *, org_id: str | None, service_id: str | None = None,
         actor: str | None = None, note: str | None = None) -> None:
    conn.execute(
        "insert into org_events (org_id, service_id, action, actor, note) values (%s, %s, %s, %s, %s)",
        (org_id, service_id, action, actor, note),
    )


def _match_catalog_institution(name: str) -> str | None:
    wanted = name.strip().lower()
    try:
        for inst in catalog_service.list_institutions():
            if wanted in {(inst.get("name") or "").lower(), (inst.get("short_name") or "").lower()}:
                return inst["id"]
    except Exception:
        log.exception("Catalog lookup failed")
    return None


# ---------------------------------------------------------------- organizations


REPRESENTATIVE_FIELDS = ("representative_name", "representative_title", "official_email")


def register_org(fields: dict, *, user_id: str, user_email: str) -> dict:
    """Create an organization. draft=True saves a registration the person finishes later."""
    branches = fields.pop("branches", [])
    draft = bool(fields.pop("draft", False))
    if not draft:
        missing = [k for k in REPRESENTATIVE_FIELDS if not fields.get(k)]
        if missing:
            raise OrgError("Add the representative's name, position and official email")
    with connection() as conn, conn.transaction():
        if fields.get("parent_org_id") and not conn.execute(
            "select 1 from organizations where id = %s", (fields["parent_org_id"],)
        ).fetchone():
            raise OrgError("Parent organization not found", 404)
        slug = _unique_slug(conn, "organizations", slugify(fields["name"]))
        cols = [*fields.keys(), "slug", "created_by", "catalog_institution_id", "status", "onboarding_step",
                "submitted_at"]
        vals = [*fields.values(), slug, user_id, _match_catalog_institution(fields["name"]),
                "draft" if draft else "pending", 1 if draft else 6, None if draft else datetime.now(timezone.utc)]
        row = conn.execute(
            f"insert into organizations ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) returning id::text",
            vals,
        ).fetchone()
        org_id = row["id"]
        conn.execute(
            """
            insert into organization_members (org_id, user_id, invited_email, role, accepted)
            values (%s, %s, lower(%s), 'owner', true)
            """,
            (org_id, user_id, user_email),
        )
        for b in branches:
            _insert_branch(conn, org_id, b)
        _log(conn, "registration_started" if draft else "registered", org_id=org_id, actor=user_email)
    return member_org(org_id)


def registration_problems(org_id: str) -> list[str]:
    """What still blocks sending a draft registration for verification."""
    org = fetch_one(f"select {MEMBER_ORG_COLUMNS} from organizations o where o.id = %s", (org_id,))
    if not org:
        raise OrgError("Organization not found", 404)
    problems = []
    if not all(org.get(k) for k in REPRESENTATIVE_FIELDS):
        problems.append("Representative name, position and official email")
    if not fetch_one("select 1 from organization_branches where org_id = %s", (org_id,)):
        problems.append("At least one branch where people get your services")
    if not org.get("steward_name") or not (org.get("steward_phone") or org.get("steward_email")):
        problems.append("Who keeps your data current, with a phone or email")
    if not org.get("data_commitment_at"):
        problems.append("The commitment to keep requirements and prices up to date")
    return problems


def submit_registration(org_id: str, *, submit_services: bool, actor: str) -> dict:
    with connection() as conn:
        org = conn.execute("select status from organizations where id = %s", (org_id,)).fetchone()
    if not org:
        raise OrgError("Organization not found", 404)
    if org["status"] != "draft":
        raise OrgError("This registration was already sent for verification", 409)
    problems = registration_problems(org_id)
    if problems:
        raise OrgError("Still missing: " + "; ".join(problems))
    with connection() as conn, conn.transaction():
        conn.execute(
            "update organizations set status = 'pending', submitted_at = now(), onboarding_step = 6, "
            "updated_at = now() where id = %s",
            (org_id,),
        )
        _log(conn, "registered", org_id=org_id, actor=actor)
    submitted, skipped = [], []
    if submit_services:
        for svc in fetch_all("select id::text, name from org_services where org_id = %s and status in "
                             "('draft', 'changes_requested')", (org_id,)):
            work = working_copy(svc["id"], org_id)
            if completeness(work)["core_missing"] or not (work.get("summary") or "").strip():
                skipped.append(svc["name"])
                continue
            submit_service(org_id, svc["id"], actor)
            submitted.append(svc["name"])
    return {"organization": member_org(org_id), "services_submitted": submitted, "services_skipped": skipped}


def _claim_invites(user_id: str, email: str) -> None:
    execute(
        """
        update organization_members set user_id = %s, accepted = true
        where lower(invited_email) = lower(%s) and user_id is null
        """,
        (user_id, email),
    )


def my_orgs(user_id: str, email: str) -> list[dict]:
    _claim_invites(user_id, email)
    return fetch_all(
        f"""
        select {MEMBER_ORG_COLUMNS}, m.role,
               (select count(*) from org_services s where s.org_id = o.id and s.status <> 'archived') as service_count
        from organizations o join organization_members m on m.org_id = o.id
        where m.user_id = %s and m.accepted
        order by o.created_at
        """,
        (user_id,),
    )


def member_role(org_id: str, user_id: str) -> str | None:
    row = fetch_one(
        "select role from organization_members where org_id = %s and user_id = %s and accepted",
        (org_id, user_id),
    )
    return row["role"] if row else None


def require_member(org_id: str, user_id: str, *, owner: bool = False, is_admin: bool = False) -> str:
    role = member_role(org_id, user_id)
    if role is None and is_admin:
        return "admin"
    if role is None:
        raise OrgError("You are not a member of this organization", 403)
    if owner and role != "owner":
        raise OrgError("Only an owner can do this", 403)
    return role


def member_org(org_id: str) -> dict | None:
    org = fetch_one(f"select {MEMBER_ORG_COLUMNS} from organizations o where o.id = %s", (org_id,))
    if not org:
        return None
    org["branches"] = list_branches(org_id)
    org["members"] = fetch_all(
        """
        select m.id::text, m.invited_email as email, m.role, m.accepted, u.fullname
        from organization_members m left join users u on u.id = m.user_id
        where m.org_id = %s order by m.created_at
        """,
        (org_id,),
    )
    return org


def update_org(org_id: str, changes: dict, actor: str) -> dict:
    commitment = changes.pop("data_commitment", None)
    changes = {k: v for k, v in changes.items() if k in ORG_EDITABLE}
    if commitment is not None:
        execute(
            "update organizations set data_commitment_at = case when %s then coalesce(data_commitment_at, now()) "
            "else null end, updated_at = now() where id = %s",
            (commitment, org_id),
        )
    if not changes:
        return member_org(org_id)
    with connection() as conn, conn.transaction():
        org = conn.execute("select status from organizations where id = %s for update", (org_id,)).fetchone()
        if not org:
            raise OrgError("Organization not found", 404)
        if org["status"] == "suspended":
            raise OrgError("A suspended organization can't be edited. Contact the platform team.", 409)
        sets = ", ".join(f"{k} = %s" for k in changes)
        reset = org["status"] == "verified" and IDENTITY_FIELDS & changes.keys()
        conn.execute(
            f"update organizations set {sets}, updated_at = now()"
            + (", status = 'pending'" if reset else "")
            + " where id = %s",
            (*changes.values(), org_id),
        )
        _log(conn, "resubmitted" if reset else "updated", org_id=org_id, actor=actor)
    return member_org(org_id)


def set_org_file(org_id: str, column: str, value: str, actor: str) -> dict:
    assert column in ("logo_url", "authorization_letter_key")
    execute(f"update organizations set {column} = %s, updated_at = now() where id = %s", (value, org_id))
    with connection() as conn:
        _log(conn, f"{column}_uploaded", org_id=org_id, actor=actor)
    return member_org(org_id)


def invite_member(org_id: str, email: str, role: str, actor: str) -> dict:
    with connection() as conn, conn.transaction():
        if conn.execute(
            "select 1 from organization_members where org_id = %s and lower(invited_email) = lower(%s)",
            (org_id, email),
        ).fetchone():
            raise OrgError("This person is already a member or invited", 409)
        user = conn.execute("select id from users where lower(email) = lower(%s)", (email,)).fetchone()
        conn.execute(
            """
            insert into organization_members (org_id, user_id, invited_email, role, accepted)
            values (%s, %s, lower(%s), %s, %s)
            """,
            (org_id, user["id"] if user else None, email, role, bool(user)),
        )
        _log(conn, "member_invited", org_id=org_id, actor=actor, note=f"{email} as {role}")
    return member_org(org_id)


def remove_member(org_id: str, member_id: str, actor_user_id: str, actor: str) -> dict:
    with connection() as conn, conn.transaction():
        member = conn.execute(
            "select user_id::text, role, invited_email from organization_members where id = %s and org_id = %s",
            (member_id, org_id),
        ).fetchone()
        if not member:
            raise OrgError("Member not found", 404)
        if member["user_id"] == actor_user_id:
            raise OrgError("You can't remove yourself", 400)
        if member["role"] == "owner":
            owners = conn.execute(
                "select count(*) as c from organization_members where org_id = %s and role = 'owner' and accepted",
                (org_id,),
            ).fetchone()["c"]
            if owners <= 1:
                raise OrgError("An organization needs at least one owner", 400)
        conn.execute("delete from organization_members where id = %s", (member_id,))
        _log(conn, "member_removed", org_id=org_id, actor=actor, note=member["invited_email"])
    return member_org(org_id)


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
    return {"confirmed_days_ago": days, "confirmation_due": days >= CONFIRM_EVERY_DAYS}


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
    for r in rows:
        r.update(_confirmation(r["last_confirmed_at"], r["is_live"]))
        work = working_copy(r["id"], org_id)
        r["completeness"] = completeness(work) if work else None
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
    row = fetch_one(
        "update org_services set status = 'archived', updated_at = now() where id = %s and org_id = %s returning id",
        (service_id, org_id),
    )
    if not row:
        raise OrgError("Service not found", 404)
    execute(
        "update org_service_revisions set status = 'superseded' where service_id = %s and status in ('pending', 'scheduled')",
        (service_id,),
    )
    with connection() as conn:
        _log(conn, "service_archived", org_id=org_id, service_id=service_id, actor=actor)
    remove_service_from_graph(service_id)
    return working_copy(service_id, org_id)


SNAPSHOT_KEYS = ("id", "org_id", "slug", *SERVICE_FIELDS, "requirements", "questions", "steps")


def _snapshot(service: dict) -> dict:
    return _plain({k: service.get(k) for k in SNAPSHOT_KEYS})


# ---------------------------------------------------------------- freshness


def confirm_services(org_id: str, service_ids: list[str] | None, actor: str) -> int:
    """'Still accurate': restart the 90-day clock for live services (all of them when ids is None)."""
    rows = fetch_all(
        """
        update org_services set last_confirmed_at = now(), last_confirmed_by = %s
        where org_id = %s and published_snapshot is not null and status <> 'archived'
          and (%s::uuid[] is null or id = any(%s::uuid[]))
        returning id::text
        """,
        (actor, org_id, service_ids, service_ids),
    )
    with connection() as conn:
        for r in rows:
            _log(conn, "service_confirmed", org_id=org_id, service_id=r["id"], actor=actor)
    return len(rows)


def count_services_due_for_confirmation() -> int:
    return fetch_one(
        f"""
        select count(*) as c from org_services s join organizations o on o.id = s.org_id
        where s.published_snapshot is not null and s.status <> 'archived' and o.status = 'verified'
          and (s.last_confirmed_at is null or s.last_confirmed_at < now() - interval '{CONFIRM_EVERY_DAYS} days')
        """
    )["c"]


def services_due_for_confirmation(limit: int = 200) -> list[dict]:
    return fetch_all(
        f"""
        select s.id::text, s.name, s.last_confirmed_at, o.id::text as org_id, o.name as org_name
        from org_services s join organizations o on o.id = s.org_id
        where s.published_snapshot is not null and s.status <> 'archived' and o.status = 'verified'
          and (s.last_confirmed_at is null or s.last_confirmed_at < now() - interval '{CONFIRM_EVERY_DAYS} days')
        order by s.last_confirmed_at nulls first
        limit %s
        """,
        (limit,),
    )


# ---------------------------------------------------------------- review (staff)


def review_org(org_id: str, action: str, *, actor: str, note: str | None,
               catalog_institution_id: str | None = None) -> dict:
    allowed_from, new_status = ORG_ACTIONS[action]
    if action in NOTE_REQUIRED and not (note or "").strip():
        raise OrgError("Add a note explaining the decision")
    with connection() as conn, conn.transaction():
        org = conn.execute("select status from organizations where id = %s for update", (org_id,)).fetchone()
        if not org:
            raise OrgError("Organization not found", 404)
        if org["status"] not in allowed_from:
            raise OrgError(f"Can't {action} an organization that is {org['status']}", 409)
        conn.execute(
            """
            update organizations set status = %s, verification_note = %s, reviewed_by = %s, reviewed_at = now(),
              catalog_institution_id = coalesce(%s, catalog_institution_id), updated_at = now()
            where id = %s
            """,
            (new_status, note, actor, catalog_institution_id, org_id),
        )
        _log(conn, action, org_id=org_id, actor=actor, note=note)
    if new_status == "verified":
        for s in fetch_all("select id::text from org_services where org_id = %s and published_snapshot is not null "
                           "and status <> 'archived'", (org_id,)):
            sync_service_to_graph(s["id"])
    return admin_org(org_id)


def admin_org(org_id: str) -> dict | None:
    org = fetch_one(f"select {ADMIN_ORG_COLUMNS} from organizations o where o.id = %s", (org_id,))
    if not org:
        return None
    org["branches"] = list_branches(org_id)
    org["services"] = list_org_services(org_id)
    org["members"] = member_org(org_id)["members"]
    org["events"] = fetch_all(
        "select action, actor, note, created_at, service_id::text from org_events where org_id = %s "
        "order by created_at desc limit 100",
        (org_id,),
    )
    return org


def list_orgs_admin(status: str | None, q: str | None, limit: int, offset: int) -> dict:
    where, params = ["true"], []
    if status and status != "all":
        where.append("o.status = %s")
        params.append(status)
    if q:
        where.append("(o.name ilike %s or o.name_am ilike %s or o.official_email ilike %s)")
        params += [f"%{q}%"] * 3
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from organizations o where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select {MEMBER_ORG_COLUMNS},
          (select count(*) from org_services s where s.org_id = o.id and s.published_snapshot is not null
             and s.status <> 'archived') as live_services,
          (select count(*) from org_services s where s.org_id = o.id and s.published_snapshot is not null
             and s.status <> 'archived' and (s.last_confirmed_at is null
             or s.last_confirmed_at < now() - interval '90 days')) as services_due,
          (select count(*) from feedback_flags f where f.org_id = o.id and f.status = 'open') as open_reports
        from organizations o where {clause} order by o.created_at desc limit %s offset %s
        """,
        [*params, limit, offset],
    )
    for org in items:
        scores = [completeness(working_copy(s["id"]))["score"] for s in
                  fetch_all("select id::text from org_services where org_id = %s and status <> 'archived'", (org["id"],))]
        org["completeness"] = round(sum(scores) / len(scores)) if scores else None
    return {"total": total, "items": items}


def count_submissions(status: str = "pending") -> int:
    return fetch_one("select count(*) as c from org_service_revisions r where (%s = 'all' or r.status = %s)",
                     (status, status))["c"]


def list_submissions(status: str = "pending", limit: int = 50, offset: int = 0) -> list[dict]:
    return fetch_all(
        """
        select r.id::text, r.status, r.submitted_by, r.created_at, r.reviewed_at, r.admin_note,
               r.change_summary, r.effective_at,
               s.id::text as service_id, s.name as service_name, (s.published_snapshot is not null) as is_update,
               o.id::text as org_id, o.name as org_name, o.status as org_status
        from org_service_revisions r
        join org_services s on s.id = r.service_id
        join organizations o on o.id = s.org_id
        where (%s = 'all' or r.status = %s)
        order by r.created_at desc limit %s offset %s
        """,
        (status, status, limit, offset),
    )


def submission_detail(revision_id: str) -> dict | None:
    row = fetch_one(
        """
        select r.id::text, r.status, r.snapshot, r.submitted_by, r.created_at, r.admin_note, r.reviewed_by,
               r.change_summary, r.change_reason, r.effective_at, r.live_at,
               s.id::text as service_id, s.published_snapshot, s.version,
               o.id::text as org_id, o.name as org_name, o.slug as org_slug, o.status as org_status
        from org_service_revisions r
        join org_services s on s.id = r.service_id
        join organizations o on o.id = s.org_id
        where r.id = %s
        """,
        (revision_id,),
    )
    if not row:
        return None
    row["completeness"] = completeness(row["snapshot"])
    return _plain(row)


def review_submission(revision_id: str, action: str, *, actor: str, note: str | None) -> dict:
    if action in NOTE_REQUIRED and not (note or "").strip():
        raise OrgError("Tell the organization what to change")
    went_live = scheduled = False
    with connection() as conn, conn.transaction():
        rev = conn.execute(
            """
            select r.id::text, r.status, r.snapshot, r.service_id::text, r.effective_at, r.change_summary,
                   s.org_id::text, o.status as org_status
            from org_service_revisions r join org_services s on s.id = r.service_id
            join organizations o on o.id = s.org_id
            where r.id = %s for update of r
            """,
            (revision_id,),
        ).fetchone()
        if not rev:
            raise OrgError("Submission not found", 404)
        if rev["status"] != "pending":
            raise OrgError(f"This submission is already {rev['status'].replace('_', ' ')}", 409)
        if action == "publish":
            if rev["org_status"] != "verified":
                raise OrgError("Verify the organization before publishing its services", 409)
            gaps = completeness(rev["snapshot"])["core_missing"]
            if gaps:
                raise OrgError("Can't publish yet. Missing: " + "; ".join(gaps), 409)
            if rev["effective_at"] and rev["effective_at"] > date.today():
                conn.execute(
                    "update org_service_revisions set status = 'scheduled', reviewed_by = %s, reviewed_at = now(), "
                    "admin_note = %s where id = %s",
                    (actor, note, revision_id),
                )
                conn.execute(
                    "update org_services set status = 'scheduled', admin_note = %s, updated_at = now() where id = %s",
                    (note, rev["service_id"]),
                )
                scheduled = True
            else:
                _go_live(conn, rev, actor=actor, note=note)
                went_live = True
        else:
            conn.execute(
                "update org_services set status = 'changes_requested', admin_note = %s, updated_at = now() where id = %s",
                (note, rev["service_id"]),
            )
            conn.execute(
                "update org_service_revisions set status = 'changes_requested', reviewed_by = %s, reviewed_at = now(), "
                "admin_note = %s where id = %s",
                (actor, note, revision_id),
            )
        action_name = "service_scheduled" if scheduled else "service_published" if went_live else "changes_requested"
        _log(conn, action_name, org_id=rev["org_id"], service_id=rev["service_id"], actor=actor, note=note)
    if went_live:
        sync_service_to_graph(rev["service_id"])
        _notify_change(rev, upcoming=False)
    if scheduled:
        _notify_change(rev, upcoming=True)
    return submission_detail(revision_id)


def _go_live(conn, rev: dict, *, actor: str, note: str | None) -> None:
    """Make a revision the public version and restart the confirmation clock."""
    conn.execute(
        """
        update org_services set published_snapshot = %s, published_at = now(), version = version + 1,
          status = case when status in ('submitted', 'scheduled') then 'published' else status end,
          admin_note = coalesce(%s, admin_note), last_confirmed_at = now(), last_confirmed_by = %s,
          updated_at = now()
        where id = %s
        """,
        (Jsonb(rev["snapshot"]), note, actor, rev["service_id"]),
    )
    conn.execute(
        "update org_service_revisions set status = 'published', reviewed_by = coalesce(reviewed_by, %s), "
        "reviewed_at = coalesce(reviewed_at, now()), admin_note = coalesce(admin_note, %s), live_at = now() "
        "where id = %s",
        (actor, note, rev["id"]),
    )


def _notify_change(rev: dict, *, upcoming: bool) -> None:
    """Tell people whose saved paths use this service. First publications have nothing to announce."""
    if not rev.get("change_summary"):
        return
    try:
        from services import notifications

        snap = rev["snapshot"]
        docs = [o["document_id"] for o in snap.get("outputs") or [] if o.get("document_id")]
        owners = notifications.roadmap_owners_for_documents(docs)
        org = fetch_one("select name, slug from organizations where id = %s", (rev["org_id"],))
        when = rev["effective_at"].isoformat() if upcoming and rev.get("effective_at") else None
        title = (f"Coming {when}: change to {snap['name']}" if upcoming else f"Updated: {snap['name']}")
        notifications.notify(
            owners,
            kind="service_change_upcoming" if upcoming else "service_changed",
            title=title,
            body=f"{org['name']}: {rev['change_summary']}",
            link=f"/organizations/{org['slug']}/services/{snap['slug']}",
        )
    except Exception:
        log.exception("Could not notify users about a change to %s", rev["service_id"])


_last_promotion = 0.0


def promote_due_changes(force: bool = False) -> int:
    """Put approved changes live once their effective date arrives. Cheap enough to call on reads."""
    global _last_promotion
    if not force and time.monotonic() - _last_promotion < 60:
        return 0
    _last_promotion = time.monotonic()
    due = fetch_all(
        "select id::text from org_service_revisions where status = 'scheduled' and effective_at <= current_date"
    )
    promoted = 0
    for d in due:
        with connection() as conn, conn.transaction():
            rev = conn.execute(
                """
                select r.id::text, r.status, r.snapshot, r.service_id::text, r.effective_at, r.change_summary,
                       s.org_id::text
                from org_service_revisions r join org_services s on s.id = r.service_id
                where r.id = %s and r.status = 'scheduled' for update of r
                """,
                (d["id"],),
            ).fetchone()
            if not rev:
                continue
            _go_live(conn, rev, actor="schedule", note=None)
            _log(conn, "service_published", org_id=rev["org_id"], service_id=rev["service_id"], actor="schedule",
                 note=f"Scheduled change effective {rev['effective_at']}")
        sync_service_to_graph(rev["service_id"])
        _notify_change(rev, upcoming=False)
        promoted += 1
    return promoted


def admin_counts() -> dict:
    return fetch_one(
        """
        select
          (select count(*) from organizations) as organizations,
          (select count(*) from organizations where status = 'verified') as verified,
          (select count(*) from organizations where status = 'pending') as pending_orgs,
          (select count(*) from org_service_revisions where status = 'pending') as pending_submissions,
          (select count(*) from org_services where published_snapshot is not null and status <> 'archived') as live_services,
          (select count(*) from org_service_revisions where status = 'scheduled') as scheduled_changes,
          (select count(*) from org_services where published_snapshot is not null and status <> 'archived'
             and (last_confirmed_at is null or last_confirmed_at < now() - interval '90 days')) as services_due,
          (select count(*) from feedback_flags where org_id is not null and status = 'open') as open_reports
        """
    )


# ---------------------------------------------------------------- public reads


LIVE_FILTER = "s.published_snapshot is not null and s.status <> 'archived' and o.status = 'verified'"


def public_orgs(*, org_type: str | None, sector: str | None, region: str | None, q: str | None,
                limit: int, offset: int) -> dict:
    where, params = ["o.status = 'verified'"], []
    for col, val in (("o.org_type", org_type), ("o.sector", sector)):
        if val:
            where.append(f"{col} = %s")
            params.append(val)
    if region:
        where.append("(o.region ilike %s or o.sub_city ilike %s)")
        params += [region, region]
    if q:
        where.append("(o.name ilike %s or o.name_am ilike %s or o.description ilike %s or exists ("
                     "select 1 from org_services s where s.org_id = o.id and s.published_snapshot is not null "
                     "and s.status <> 'archived' and s.published_snapshot->>'name' ilike %s))")
        params += [f"%{q}%"] * 4
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from organizations o where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select {PUBLIC_ORG_COLUMNS},
          (select count(*) from org_services s where s.org_id = o.id and s.published_snapshot is not null
             and s.status <> 'archived') as service_count,
          (select count(*) from organization_branches b where b.org_id = o.id) as branch_count
        from organizations o where {clause} order by o.name limit %s offset %s
        """,
        [*params, limit, offset],
    )
    return {"total": total, "items": items}


def _public_service_summary(snap: dict) -> dict:
    keep = ("id", "slug", "name", "name_am", "summary", "delivery", "fee_amount_min", "fee_amount_max",
            "fee_currency", "processing_time_text", "processing_minutes", "is_free", "audience")
    return {k: snap.get(k) for k in keep}


def public_org(slug: str) -> dict | None:
    org = fetch_one(f"select {PUBLIC_ORG_COLUMNS} from organizations o where o.slug = %s and o.status = 'verified'",
                    (slug,))
    if not org:
        return None
    org["branches"] = list_branches(org["id"])
    promote_due_changes()
    rows = fetch_all(
        "select s.published_snapshot, s.last_confirmed_at from org_services s join organizations o on o.id = s.org_id "
        f"where s.org_id = %s and {LIVE_FILTER} order by s.published_snapshot->>'name'",
        (org["id"],),
    )
    org["services"] = [
        {**_public_service_summary(r["published_snapshot"]), **_confirmation(r["last_confirmed_at"], True)}
        for r in rows
    ]
    for b in org["branches"]:
        b["hours_text"] = hours_text(b.get("hours_schedule")) or b.get("hours")
    return _plain(org)


def _live_services() -> dict[str, dict]:
    """Every published service with its organization, keyed by service id."""
    promote_due_changes()
    rows = fetch_all(
        f"""
        select s.id::text, s.published_snapshot as snap, o.id::text as org_id, o.name as org_name,
               o.slug as org_slug, o.org_type
        from org_services s join organizations o on o.id = s.org_id
        where {LIVE_FILTER}
        """
    )
    return {
        r["id"]: {**r["snap"], "org": {"id": r["org_id"], "name": r["org_name"], "slug": r["org_slug"],
                                         "org_type": r["org_type"]}}
        for r in rows
    }


def _issuer_index(live: dict[str, dict]) -> dict[str, str]:
    """Graph document id -> the published service that issues it."""
    index: dict[str, str] = {}
    for sid, snap in live.items():
        for out in snap.get("outputs") or []:
            if out.get("document_id"):
                index.setdefault(out["document_id"], sid)
    return index


def _issuer_for(req: dict, own_id: str, live: dict, index: dict) -> str | None:
    issuer = req.get("issuing_service_id")
    if not issuer and req.get("document_id"):
        issuer = index.get(req["document_id"])
    return issuer if issuer and issuer != own_id and issuer in live else None


def _service_branches(snap: dict) -> list[dict]:
    """Branches that offer the service, each with its window, phone and notes for this service."""
    branch_ids = snap.get("branch_ids") or []
    if not branch_ids:
        return []
    details = {d["branch_id"]: d for d in snap.get("branch_details") or []}
    out = []
    for b in list_branches(snap["org"]["id"]):
        if b["id"] not in branch_ids:
            continue
        d = details.get(b["id"], {})
        out.append({
            **_plain(b),
            "hours_text": hours_text(b.get("hours_schedule")) or b.get("hours"),
            "window": d.get("window"),
            "service_phone": d.get("phone"),
            "hours_note": d.get("hours_note"),
            "service_notes": d.get("notes"),
        })
    return out


def _freshness_and_changes(service_id: str) -> dict:
    row = fetch_one("select last_confirmed_at from org_services where id = %s", (service_id,))
    conf = _confirmation(row["last_confirmed_at"] if row else None, True)
    upcoming = fetch_one(
        """
        select effective_at, change_summary, snapshot from org_service_revisions
        where service_id = %s and status = 'scheduled' order by effective_at limit 1
        """,
        (service_id,),
    )
    log_rows = fetch_all(
        """
        select coalesce(live_at, reviewed_at) as date, change_summary as summary, effective_at
        from org_service_revisions where service_id = %s and status = 'published'
        order by coalesce(live_at, reviewed_at) desc limit 10
        """,
        (service_id,),
    )
    return _plain({
        "confirmed_at": row["last_confirmed_at"] if row else None,
        **conf,
        "upcoming_change": {
            "effective_at": upcoming["effective_at"],
            "summary": upcoming["change_summary"],
            "fee_schedule": upcoming["snapshot"].get("fee_schedule"),
            "fee_amount_min": upcoming["snapshot"].get("fee_amount_min"),
            "fee_amount_max": upcoming["snapshot"].get("fee_amount_max"),
        } if upcoming else None,
        "change_log": [{"date": r["date"], "summary": r["summary"] or "First published", "effective_at": r["effective_at"]}
                       for r in log_rows],
    })


def public_service(org_slug: str, service_slug: str) -> dict | None:
    row = fetch_one(
        f"""
        select s.id::text from org_services s join organizations o on o.id = s.org_id
        where o.slug = %s and s.slug = %s and {LIVE_FILTER}
        """,
        (org_slug, service_slug),
    )
    if not row:
        return None
    live = _live_services()
    snap = live.get(row["id"])
    if not snap:
        return None
    index = _issuer_index(live)
    service = dict(snap)
    service["requirements"] = [_with_issuer(r, row["id"], live, index) for r in snap.get("requirements") or []]
    service["branches"] = _service_branches(snap)
    service.update(_freshness_and_changes(row["id"]))
    renewal = snap.get("renewal_service_id")
    service["renewal_service"] = (
        {"name": live[renewal]["name"], "slug": live[renewal]["slug"], "org_slug": live[renewal]["org"]["slug"]}
        if renewal and renewal in live else None
    )
    record_stat(row["id"], "view")
    return service


def _with_issuer(req: dict, own_id: str, live: dict, index: dict) -> dict:
    issuer = _issuer_for(req, own_id, live, index)
    out = dict(req)
    out.pop("issuing_service_id", None)
    out["issued_by"] = None
    if issuer:
        snap = live[issuer]
        out["issued_by"] = {"service_id": issuer, "service_name": snap["name"], "service_slug": snap["slug"],
                            "org_name": snap["org"]["name"], "org_slug": snap["org"]["slug"]}
    return out


def service_path(service_id: str, include_keys: set[str] | None = None) -> dict:
    """Every service to complete first, across organizations, prerequisites before dependents.

    include_keys limits the starting service to those requirement keys (after the
    eligibility questions); prerequisites further down always use their full list.
    Cycles are reported and broken instead of looping.
    """
    live = _live_services()
    if service_id not in live:
        raise OrgError("Service not found", 404)
    index = _issuer_index(live)
    order: list[str] = []
    done: set[str] = set()
    visiting: list[str] = []
    cycles: list[list[str]] = []
    needed_by: dict[str, list[str]] = {}

    def visit(sid: str, keys: set[str] | None) -> None:
        if sid in done:
            return
        if sid in visiting:
            cycles.append(visiting[visiting.index(sid):] + [sid])
            return
        visiting.append(sid)
        for req in live[sid].get("requirements") or []:
            if keys is not None and req["key"] not in keys:
                continue
            issuer = _issuer_for(req, sid, live, index)
            if issuer:
                needed_by.setdefault(issuer, []).append(req["name"])
                visit(issuer, None)
        visiting.pop()
        done.add(sid)
        order.append(sid)

    visit(service_id, include_keys)
    steps = []
    for sid in order:
        snap = live[sid]
        steps.append({
            "service_id": sid,
            "name": snap["name"],
            "slug": snap["slug"],
            "org": snap["org"],
            "fee_amount_min": snap.get("fee_amount_min"),
            "fee_amount_max": snap.get("fee_amount_max"),
            "fee_currency": snap.get("fee_currency"),
            "processing_time_text": snap.get("processing_time_text"),
            "processing_minutes": snap.get("processing_minutes"),
            "provides": needed_by.get(sid, []),
            "is_target": sid == service_id,
        })
    names = {sid: live[sid]["name"] for sid in live}
    return {
        "steps": steps,
        "organizations": len({s["org"]["id"] for s in steps}),
        "total_minutes": sum(s["processing_minutes"] or 0 for s in steps),
        "cycles": [[names.get(s, s) for s in c] for c in cycles],
    }


def _rule_matches(rule: dict, answer: Any, qtype: str) -> bool:
    if isinstance(answer, bool):
        answer = "yes" if answer else "no"
    op, value = rule.get("op", "eq"), rule["value"]
    if qtype == "number" and op != "eq":
        try:
            a, v = float(answer), float(value)
        except (TypeError, ValueError):
            return False
        return {"gt": a > v, "gte": a >= v, "lt": a < v, "lte": a <= v}[op]
    return str(answer).strip().lower() == str(value).strip().lower()


def check_eligibility(service_id: str, answers: dict) -> dict:
    live = _live_services()
    snap = live.get(service_id)
    if not snap:
        raise OrgError("Service not found", 404)
    index = _issuer_index(live)
    reqs = snap.get("requirements") or []
    included = {r["key"] for r in reqs if r["required"] == "always"}
    reasons: list[str] = []
    unanswered: list[str] = []
    for q in snap.get("questions") or []:
        answer = answers.get(q["key"])
        if answer is None or answer == "":
            unanswered.append(q["key"])
            continue
        for rule in q.get("rules") or []:
            if _rule_matches(rule, answer, q["type"]):
                included |= set(rule.get("add_requirements") or [])
                if rule.get("ineligible"):
                    reasons.append(rule["ineligible"])
    checklist = [_with_issuer(r, service_id, live, index) for r in reqs if r["key"] in included]
    record_stat(service_id, "eligibility_check")
    return {
        "eligible": not reasons,
        "ineligible_reasons": reasons,
        "unanswered": unanswered,
        "checklist": checklist,
        "path": service_path(service_id, included) if not reasons else None,
    }


def requirement_options(q: str | None, limit: int = 20) -> dict:
    """What a requirement can link to: published services from any organization, and graph documents."""
    live = _live_services()
    needle = (q or "").strip().lower()
    services = [
        {"service_id": sid, "name": s["name"], "org_name": s["org"]["name"],
         "outputs": [o["name"] for o in s.get("outputs") or []]}
        for sid, s in live.items()
        if not needle or needle in s["name"].lower() or needle in s["org"]["name"].lower()
        or any(needle in (o.get("name") or "").lower() for o in s.get("outputs") or [])
    ][:limit]
    documents: list[dict] = []
    try:
        from services.graph_admin import list_documents

        documents = [
            {"document_id": d["id"], "name": d.get("name"), "issuing_authority": d.get("issuing_authority")}
            for d in list_documents()
            if not needle or needle in (d.get("name") or "").lower() or needle in d["id"]
        ][:limit]
    except Exception:
        log.exception("Graph unavailable for requirement options")
    return {"services": services, "documents": documents}


# ---------------------------------------------------------------- analytics


def record_stat(service_id: str, metric: str) -> None:
    try:
        execute(
            """
            insert into org_service_stats (service_id, metric, day, count) values (%s, %s, current_date, 1)
            on conflict (service_id, metric, day) do update set count = org_service_stats.count + 1
            """,
            (service_id, metric),
        )
    except Exception:
        log.exception("Could not record %s for %s", metric, service_id)


def org_analytics(org_id: str) -> dict:
    rows = fetch_all(
        """
        select s.id::text as service_id, s.name,
          coalesce(sum(st.count) filter (where st.metric = 'view'), 0) as views,
          coalesce(sum(st.count) filter (where st.metric = 'eligibility_check'), 0) as eligibility_checks,
          coalesce(sum(st.count) filter (where st.metric = 'path_view'), 0) as path_views,
          coalesce(sum(st.count) filter (where st.day > current_date - 30), 0) as last_30_days
        from org_services s left join org_service_stats st on st.service_id = s.id
        where s.org_id = %s and s.status <> 'archived'
        group by s.id, s.name order by views desc
        """,
        (org_id,),
    )
    return {"services": rows}


# ---------------------------------------------------------------- knowledge graph


def sync_service_to_graph(service_id: str) -> bool:
    """Mirror a published service into Neo4j. Failures are logged; Postgres stays the source of truth."""
    row = fetch_one(
        """
        select s.published_snapshot as snap, o.id::text as org_id, o.name as org_name, o.slug as org_slug,
               o.org_type, o.catalog_institution_id
        from org_services s join organizations o on o.id = s.org_id
        where s.id = %s and s.published_snapshot is not null
        """,
        (service_id,),
    )
    if not row:
        return False
    snap = row["snap"]
    try:
        from services.graph_service import _query_rows

        _query_rows(
            """
            MERGE (o:Organization {id: $org_id})
            SET o.name = $org_name, o.slug = $org_slug, o.org_type = $org_type
            WITH o
            OPTIONAL MATCH (i:Institution {id: $inst})
            FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END | MERGE (o)-[:SAME_AS]->(i))
            MERGE (s:OrgService {id: $sid})
            SET s.name = $name, s.slug = $slug, s.fee_min = $fee, s.processing_minutes = $minutes,
                s.published = true
            MERGE (s)-[:OFFERED_BY]->(o)
            WITH s
            OPTIONAL MATCH (s)-[old:REQUIRES|ISSUES|PREREQUISITE]->()
            DELETE old
            """,
            {"org_id": row["org_id"], "org_name": row["org_name"], "org_slug": row["org_slug"],
             "org_type": row["org_type"], "inst": row["catalog_institution_id"] or "", "sid": service_id,
             "name": snap["name"], "slug": snap["slug"], "fee": snap.get("fee_amount_min"),
             "minutes": snap.get("processing_minutes")},
        )
        # Linked documents reuse the compliance graph's :Document nodes; free-text ones get an :OrgDocument
        reqs = snap.get("requirements") or []
        linked = [{"key": r["key"], "doc": r["document_id"], "conditional": r["required"] == "conditional"}
                  for r in reqs if r.get("document_id")]
        free = [{"key": r["key"], "name": r["name"], "conditional": r["required"] == "conditional"}
                for r in reqs if not r.get("document_id")]
        prereqs = sorted({r["issuing_service_id"] for r in reqs if r.get("issuing_service_id")})
        params = {"sid": service_id}
        _query_rows(
            """
            UNWIND $rows AS r
            MATCH (s:OrgService {id: $sid}), (d:Document {id: r.doc})
            MERGE (s)-[rel:REQUIRES]->(d) SET rel.conditional = r.conditional, rel.key = r.key
            """,
            {**params, "rows": linked},
        )
        _query_rows(
            """
            UNWIND $rows AS r
            MATCH (s:OrgService {id: $sid})
            MERGE (d:OrgDocument {key: toLower(trim(r.name))}) ON CREATE SET d.name = r.name
            MERGE (s)-[rel:REQUIRES]->(d) SET rel.conditional = r.conditional, rel.key = r.key
            """,
            {**params, "rows": free},
        )
        _query_rows(
            """
            UNWIND $rows AS pid
            MATCH (s:OrgService {id: $sid})
            MERGE (p:OrgService {id: pid})
            MERGE (s)-[:PREREQUISITE]->(p)
            """,
            {**params, "rows": prereqs},
        )
        outs = snap.get("outputs") or []
        _query_rows(
            """
            UNWIND $rows AS o
            MATCH (s:OrgService {id: $sid}), (d:Document {id: o.doc})
            MERGE (s)-[:ISSUES]->(d)
            """,
            {**params, "rows": [{"doc": o["document_id"]} for o in outs if o.get("document_id")]},
        )
        _query_rows(
            """
            UNWIND $rows AS o
            MATCH (s:OrgService {id: $sid})
            MERGE (d:OrgDocument {key: toLower(trim(o.name))}) ON CREATE SET d.name = o.name
            MERGE (s)-[:ISSUES]->(d)
            """,
            {**params, "rows": [{"name": o["name"]} for o in outs if not o.get("document_id")]},
        )
        return True
    except Exception:
        log.exception("Graph sync failed for org service %s", service_id)
        return False


def remove_service_from_graph(service_id: str) -> None:
    try:
        from services.graph_service import _query_rows

        _query_rows("MATCH (s:OrgService {id: $sid}) DETACH DELETE s", {"sid": service_id})
    except Exception:
        log.exception("Graph removal failed for org service %s", service_id)


# ---------------------------------------------------------------- reports from citizens


def org_reports(org_id: str, status: str | None = None) -> list[dict]:
    """'This information is wrong' reports about the organization's services."""
    return _plain(fetch_all(
        """
        select f.id::text, f.target_id as service_id, s.name as service_name, f.message, f.status,
               f.org_response, f.org_responded_by, f.org_responded_at, f.created_at
        from feedback_flags f left join org_services s on s.id::text = f.target_id
        where f.org_id = %s and (%s::text is null or f.status = %s)
        order by (f.status = 'open') desc, f.created_at desc limit 200
        """,
        (org_id, status, status),
    ))


def respond_report(org_id: str, flag_id: str, *, status: str, response: str, actor: str) -> dict:
    row = fetch_one(
        """
        update feedback_flags set status = %s, org_response = %s, org_responded_by = %s, org_responded_at = now(),
          resolution_note = case when %s <> 'open' then %s else resolution_note end,
          resolved_by = case when %s <> 'open' then %s else resolved_by end,
          resolved_at = case when %s <> 'open' then now() else resolved_at end
        where id::text = %s and org_id = %s
        returning id::text
        """,
        (status, response, actor, status, response, status, actor, status, flag_id, org_id),
    )
    if not row:
        raise OrgError("Report not found", 404)
    with connection() as conn:
        _log(conn, f"report_{status}", org_id=org_id, actor=actor, note=response[:200])
    return next(r for r in org_reports(org_id) if r["id"] == flag_id)


def org_for_service(service_id: str) -> str | None:
    row = fetch_one("select org_id::text from org_services where id::text = %s", (service_id,))
    return row["org_id"] if row else None


# ---------------------------------------------------------------- paths (roadmap steps)


def _norm_place(value: str | None) -> str:
    return re.sub(r"[^a-z]", "", (value or "").lower())


def org_data_for_steps(document_ids: list[str], sub_city: str | None) -> dict[str, dict]:
    """For each roadmap step (a document id), what the issuing organization published about it.

    Picks the service that issues the document, preferring one with a branch in the
    person's sub-city, and returns everything the step should show.
    """
    wanted = set(document_ids)
    if not wanted:
        return {}
    live = _live_services()
    here = _norm_place(sub_city)
    best: dict[str, tuple[int, str]] = {}
    for sid, snap in live.items():
        branches = _service_branches(snap)
        local = any(_norm_place(b.get("sub_city")) == here for b in branches) if here else False
        rank = (2 if local else 0) + (1 if branches else 0)
        for out in snap.get("outputs") or []:
            doc = out.get("document_id")
            if doc in wanted and (doc not in best or rank > best[doc][0]):
                best[doc] = (rank, sid)
    if not best:
        return {}
    index = _issuer_index(live)
    result = {}
    for doc, (_, sid) in best.items():
        snap = live[sid]
        branches = _service_branches(snap)
        branches.sort(key=lambda b: _norm_place(b.get("sub_city")) != here)
        fresh = _freshness_and_changes(sid)
        result[doc] = _plain({
            "serviceId": sid,
            "serviceName": snap["name"],
            "serviceNameAm": snap.get("name_am"),
            "orgName": snap["org"]["name"],
            "orgSlug": snap["org"]["slug"],
            "serviceSlug": snap["slug"],
            "summary": snap.get("summary"),
            "branch": branches[0] if branches else None,
            "otherBranches": len(branches) - 1 if branches else 0,
            "delivery": snap.get("delivery"),
            "onlineUrl": snap.get("online_url"),
            "onlineParts": snap.get("online_parts"),
            "isFree": snap.get("is_free"),
            "feeSchedule": snap.get("fee_schedule") or [],
            "feeAmountMin": snap.get("fee_amount_min"),
            "feeAmountMax": snap.get("fee_amount_max"),
            "feeCurrency": snap.get("fee_currency") or "ETB",
            "feeNotes": snap.get("fee_notes"),
            "paymentMethods": snap.get("payment_methods") or [],
            "whereToPay": snap.get("where_to_pay"),
            "processingTimeText": snap.get("processing_time_text"),
            "processingMinutes": snap.get("processing_minutes"),
            "requirements": [
                {k: v for k, v in _with_issuer(r, sid, live, index).items() if k not in ("key", "kind", "document_id")}
                for r in snap.get("requirements") or []
            ],
            "noDocumentsRequired": snap.get("no_documents_required"),
            "hasQuestions": bool(snap.get("questions")),
            "steps": snap.get("steps") or [],
            "appointment": {
                "required": snap.get("appointment_required"),
                "how": snap.get("appointment_how"),
                "url": snap.get("appointment_url"),
                "phone": snap.get("appointment_phone"),
            },
            "proxyAllowed": snap.get("proxy_allowed"),
            "proxyNotes": snap.get("proxy_notes"),
            "languages": snap.get("languages") or [],
            "accessibilityNotes": snap.get("accessibility_notes"),
            "legalBasis": snap.get("legal_basis"),
            "legalReferenceNumber": snap.get("legal_reference_number"),
            "forms": snap.get("forms") or [],
            "rejectionReasons": snap.get("common_rejection_reasons") or [],
            "outputValidityMonths": snap.get("output_validity_months"),
            "lateRenewalPenalty": snap.get("late_renewal_penalty"),
            "contact": {"name": snap.get("contact_name"), "phone": snap.get("contact_phone"),
                        "email": snap.get("contact_email")},
            "confirmedAt": fresh["confirmed_at"],
            "confirmedDaysAgo": fresh["confirmed_days_ago"],
            "confirmationDue": fresh["confirmation_due"],
            "upcomingChange": fresh["upcoming_change"],
        })
    return result
