"""Organizations: registration, members and invites."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from services.db import connection, execute, fetch_all, fetch_one
from .branches import _insert_branch, list_branches
from .helpers import (
    IDENTITY_FIELDS,
    MEMBER_ORG_COLUMNS,
    ORG_EDITABLE,
    OrgError,
    _log,
    _match_catalog_institution,
    _plain,
    _unique_slug,
    slugify,
)
from .services_edit import completeness, submit_service, working_copy

log = logging.getLogger(__name__)


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


def my_invites(email: str) -> list[dict]:
    """Invitations waiting for this person to accept or decline. Nobody joins an organization without saying yes."""
    return _plain(fetch_all(
        """
        select m.id::text, m.role, m.created_at, o.id::text as org_id, o.name as org_name, o.name_am as org_name_am,
               o.logo_url, o.status as org_status
        from organization_members m join organizations o on o.id = m.org_id
        where lower(m.invited_email) = lower(%s) and not m.accepted
        order by m.created_at desc
        """,
        (email,),
    ))


def answer_invite(member_id: str, *, user_id: str, email: str, accept: bool) -> dict:
    with connection() as conn, conn.transaction():
        invite = conn.execute(
            "select org_id::text, role from organization_members where id = %s and lower(invited_email) = lower(%s) "
            "and not accepted for update",
            (member_id, email),
        ).fetchone()
        if not invite:
            raise OrgError("Invitation not found", 404)
        if accept:
            conn.execute("update organization_members set user_id = %s, accepted = true where id = %s",
                         (user_id, member_id))
        else:
            conn.execute("delete from organization_members where id = %s", (member_id,))
        _log(conn, "member_joined" if accept else "invite_declined", org_id=invite["org_id"], actor=email,
             note=invite["role"])
    return {"org_id": invite["org_id"], "accepted": accept}


def my_orgs(user_id: str, email: str) -> list[dict]:
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
        select m.id::text, m.invited_email as email, m.role, m.accepted,
               case when m.accepted then u.fullname end as fullname
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
        # Always a pending invitation, whether or not the email has an account: the answer must not reveal it
        conn.execute(
            """
            insert into organization_members (org_id, user_id, invited_email, role, accepted)
            values (%s, null, lower(%s), %s, false)
            """,
            (org_id, email, role),
        )
        _log(conn, "member_invited", org_id=org_id, actor=actor, note=f"{email} as {role}")
        org = conn.execute("select name from organizations where id = %s", (org_id,)).fetchone()
        user = conn.execute("select id::text from users where lower(email) = lower(%s)", (email,)).fetchone()
    if user:
        try:
            from services import notifications

            notifications.notify([user["id"]], kind="org_invite", title=f"Invitation to join {org['name']}",
                                 body=f"{actor} invited you as {role}. Accept or decline it on your organization page.",
                                 link="/org")
        except Exception:
            log.exception("Could not notify an invited member of %s", org_id)
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
