"""
Managing staff and roles: the rules behind the Access pages of the admin app.

Hierarchy rules enforced here (see docs/staff-access.md):
  - nobody changes their own roles, status or permissions
  - you can only hand out permissions you hold yourself (no privilege escalation)
  - only a Super admin can change another Super admin
  - at least one active Super admin always exists
  - built-in roles are read-only
Risky changes go through services/approvals.py; the exec_* functions below are what runs once
they are approved (or straight away when nobody else could approve). They check the rules again,
because things may have changed while the request waited.
"""

from __future__ import annotations

from psycopg.errors import UniqueViolation

from auth import staff_service
from auth.service import ClientInfo
from schemas.staff_user import StaffActor
from services import access, approvals
from services.db import connection, fetch_all, fetch_one


class StaffAdminError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------- roles


def _role_row(role_id: str) -> dict | None:
    try:
        return fetch_one("select id::text, name, description, builtin_key, created_by, created_at, updated_at "
                         "from staff_roles where id = %s", (role_id,))
    except Exception:
        return None


def _role_view(role: dict) -> dict:
    perms = sorted(access.role_permissions(role))
    members = fetch_one("select count(*) as n from staff_user_roles ur join staff_users s on s.id = ur.staff_id "
                        "where ur.role_id = %s and s.status <> 'disabled'", (role["id"],))["n"]
    return {**role, "built_in": bool(role["builtin_key"]), "permissions": perms, "members": members}


def list_roles(limit: int = 50, offset: int = 0) -> dict:
    rows = fetch_all("select id::text, name, description, builtin_key, created_by, created_at, updated_at "
                     "from staff_roles order by builtin_key is null, name limit %s offset %s", (limit, offset))
    total = fetch_one("select count(*) as n from staff_roles")["n"]
    return {"items": [_role_view(r) for r in rows], "total": total}


def get_role(role_id: str) -> dict | None:
    role = _role_row(role_id)
    if not role:
        return None
    view = _role_view(role)
    view["staff"] = fetch_all(
        """
        select s.id::text, s.email, s.fullname, s.status from staff_user_roles ur join staff_users s on s.id = ur.staff_id
        where ur.role_id = %s order by s.email
        """,
        (role_id,),
    )
    return view


def _clean_permissions(permissions: list[str], actor: StaffActor) -> list[str]:
    unknown = [p for p in permissions if p not in access.BY_KEY]
    if unknown:
        raise StaffAdminError(f"Unknown permission: {', '.join(unknown)}", 422)
    missing = [p for p in permissions if not actor.can(p)]
    if missing:
        raise StaffAdminError("You can only give permissions you have yourself. Missing: " + ", ".join(sorted(missing)), 403)
    return sorted(set(permissions))


def _check_name(name: str, exclude_id: str | None = None) -> str:
    name = (name or "").strip()
    if not 2 <= len(name) <= 60:
        raise StaffAdminError("Role name must be 2 to 60 characters", 422)
    clash = fetch_one("select id::text from staff_roles where lower(name) = lower(%s) and id::text is distinct from %s",
                      (name, exclude_id))
    if clash:
        raise StaffAdminError("A role with this name already exists", 409)
    return name


def create_role(actor: StaffActor, name: str, description: str, permissions: list[str],
                client: ClientInfo | None = None) -> dict:
    """A new role is held by nobody yet, so it needs no second approval."""
    payload = {"name": _check_name(name), "description": (description or "").strip()[:300],
               "permissions": _clean_permissions(permissions, actor)}
    result = exec_role_create(payload, actor.email)
    staff_service.audit("role.created", actor=actor, target=f"role:{result['role_id']}", client=client, details=payload)
    return get_role(result["role_id"])


def exec_role_create(payload: dict, actor_label: str) -> dict:
    try:
        with connection() as conn, conn.transaction():
            row = conn.execute("insert into staff_roles (name, description, created_by) values (%s, %s, %s) "
                               "returning id::text", (payload["name"], payload["description"], actor_label)).fetchone()
            for perm in payload["permissions"]:
                conn.execute("insert into staff_role_permissions (role_id, permission) values (%s, %s)", (row["id"], perm))
    except UniqueViolation:
        raise StaffAdminError("A role with this name already exists", 409) from None
    return {"role_id": row["id"]}


def update_role(actor: StaffActor, role_id: str, name: str, description: str, permissions: list[str],
                client: ClientInfo | None = None) -> dict:
    """Renaming is immediate; changing permissions needs a second person."""
    role = _role_row(role_id)
    if not role:
        raise StaffAdminError("Role not found", 404)
    if role["builtin_key"]:
        raise StaffAdminError("Built-in roles can't be changed. Duplicate it and change the copy.", 403)
    name = _check_name(name, role_id)
    description = (description or "").strip()[:300]
    before = set(access.role_permissions(role))
    wanted = set(permissions)
    added, removed = sorted(wanted - before), sorted(before - wanted)
    # Removing a permission you don't hold is fine; adding one is not
    _clean_permissions(added, actor)
    unknown = [p for p in removed if p not in access.BY_KEY]
    if unknown:
        raise StaffAdminError(f"Unknown permission: {', '.join(unknown)}", 422)
    holders = [r["staff_id"] for r in fetch_all("select staff_id::text from staff_user_roles where role_id = %s", (role_id,))]
    if added and actor.id in holders:
        raise StaffAdminError("You hold this role, so you can't add permissions to it. Ask another Super admin.", 403)
    if name != role["name"] or description != role["description"]:
        fetch_one("update staff_roles set name = %s, description = %s, updated_at = now() where id = %s returning id",
                  (name, description, role_id))
        staff_service.audit("role.renamed", actor=actor, target=f"role:{role_id}", client=client,
                            details={"name": name, "before": role["name"]})
    if not added and not removed:
        return {"role": get_role(role_id)}
    labels = lambda keys: ", ".join(access.BY_KEY[k].label for k in keys if k in access.BY_KEY)  # noqa: E731
    summary = f"Change the permissions of role \"{name}\" ({len(holders)} staff hold it)."
    if added:
        summary += f" Add: {labels(added)}."
    if removed:
        summary += f" Remove: {labels(removed)}."
    outcome = approvals.request("role.update", {"role_id": role_id, "add": added, "remove": removed, "name": name},
                                summary, actor, target=f"role:{role_id}", beneficiaries=holders if added else [],
                                client=client)
    return {"role": get_role(role_id), **_outcome(outcome)}


def exec_role_update(payload: dict, actor_label: str) -> dict:
    role = _role_row(payload["role_id"])
    if not role or role["builtin_key"]:
        raise StaffAdminError("The role no longer exists or can't be changed", 409)
    with connection() as conn, conn.transaction():
        for perm in payload["add"]:
            conn.execute("insert into staff_role_permissions (role_id, permission) values (%s, %s) on conflict do nothing",
                         (role["id"], perm))
        if payload["remove"]:
            conn.execute("delete from staff_role_permissions where role_id = %s and permission = any(%s)",
                         (role["id"], payload["remove"]))
        conn.execute("update staff_roles set updated_at = now() where id = %s", (role["id"],))
    return {"role_id": role["id"], "added": payload["add"], "removed": payload["remove"]}


def delete_role(actor: StaffActor, role_id: str, client: ClientInfo | None = None) -> dict:
    role = _role_row(role_id)
    if not role:
        raise StaffAdminError("Role not found", 404)
    if role["builtin_key"]:
        raise StaffAdminError("Built-in roles can't be deleted", 403)
    holders = fetch_one("select count(*) as n from staff_user_roles where role_id = %s", (role_id,))["n"]
    if not holders:
        exec_role_delete({"role_id": role_id}, actor.email)
        staff_service.audit("role.deleted", actor=actor, target=f"role:{role_id}", client=client,
                            details={"name": role["name"]})
        return {"deleted": True}
    outcome = approvals.request("role.delete", {"role_id": role_id, "name": role["name"]},
                                f"Delete role \"{role['name']}\"; {holders} staff lose its permissions",
                                actor, target=f"role:{role_id}", client=client)
    return _outcome(outcome)


def exec_role_delete(payload: dict, actor_label: str) -> dict:
    row = fetch_one("delete from staff_roles where id = %s and builtin_key is null returning id::text",
                    (payload["role_id"],))
    if not row:
        raise StaffAdminError("The role no longer exists", 404)
    return {"deleted": row["id"]}


# ---------------------------------------------------------------- staff


def _staff_view(row: dict) -> dict:
    roles = access.staff_roles(row["id"])
    sessions = fetch_one("select count(*) as n from staff_sessions where staff_id = %s and revoked_at is null "
                         "and expires_at > now()", (row["id"],))["n"]
    invite = staff_service.pending_invite(row["id"]) if row["status"] == "invited" else None
    return {**row, "roles": [{"id": r["id"], "name": r["name"], "built_in": bool(r["builtin_key"])} for r in roles],
            "super_admin": any(r["builtin_key"] == access.SUPER_ADMIN for r in roles),
            "active_sessions": sessions, "invite": invite}


def list_staff(q: str | None = None, status: str | None = None, role_id: str | None = None,
               limit: int = 25, offset: int = 0) -> dict:
    where, params = ["true"], []
    if q:
        where.append("(s.email ilike %s or s.fullname ilike %s)")
        params += [f"%{q}%", f"%{q}%"]
    if status:
        where.append("s.status = %s")
        params.append(status)
    if role_id:
        where.append("exists (select 1 from staff_user_roles ur where ur.staff_id = s.id and ur.role_id::text = %s)")
        params.append(role_id)
    clause = " and ".join(where)
    rows = fetch_all(f"select {staff_service.STAFF_COLUMNS} from staff_users s where {clause} "
                     f"order by s.status = 'disabled', s.created_at desc limit %s offset %s", [*params, limit, offset])
    total = fetch_one(f"select count(*) as n from staff_users s where {clause}", params)["n"]
    return {"items": [_staff_view(r) for r in rows], "total": total}


def get_staff(staff_id: str, with_permissions: bool = True) -> dict | None:
    row = staff_service.get_staff(staff_id)
    if not row:
        return None
    view = _staff_view(row)
    if with_permissions:
        view["permissions"] = sorted(access.staff_permissions(staff_id))
    return view


def _target(actor: StaffActor, staff_id: str, *, allow_self: bool = False) -> dict:
    target = staff_service.get_staff(staff_id)
    if not target:
        raise StaffAdminError("Staff member not found", 404)
    if not allow_self and target["id"] == actor.id:
        raise StaffAdminError("You can't do this to your own account. Ask another Super admin.", 403)
    if access.is_super_admin(target["id"]) and not access.is_super_admin(actor.id):
        raise StaffAdminError("Only a Super admin can change a Super admin", 403)
    return target


def _roles_for(role_ids: list[str]) -> list[dict]:
    ids = sorted(set(role_ids))
    if not ids:
        return []
    try:
        rows = fetch_all("select id::text, name, builtin_key from staff_roles where id::text = any(%s)", (ids,))
    except Exception:
        rows = []
    if len(rows) != len(ids):
        raise StaffAdminError("One of the roles doesn't exist", 422)
    return rows


def _check_can_grant(actor: StaffActor, roles: list[dict]) -> None:
    for role in roles:
        missing = access.role_permissions(role) - actor.permissions
        if missing:
            raise StaffAdminError(f"You can't give the role \"{role['name']}\": it has permissions you don't have.", 403)


def _outcome(outcome: dict) -> dict:
    if "pending" in outcome:
        return {"approval": outcome["pending"]}
    return {"waived": True, "result": outcome["result"]}


def create_staff(actor: StaffActor, email: str, fullname: str, role_ids: list[str],
                 client: ClientInfo | None = None) -> dict:
    email = (email or "").strip().lower()
    if staff_service.get_staff_by_email(email):
        raise StaffAdminError("A staff member with this email already exists", 409)
    pending = fetch_one("select id from approval_requests where action = 'staff.create' and status = 'pending' "
                        "and target = %s", (f"staff-email:{email}",))
    if pending:
        raise StaffAdminError("An invitation for this email is already waiting for approval", 409)
    roles = _roles_for(role_ids)
    if not roles:
        raise StaffAdminError("Give the new staff member at least one role", 422)
    _check_can_grant(actor, roles)
    payload = {"email": email, "fullname": (fullname or "").strip()[:120], "role_ids": [r["id"] for r in roles],
               "invited_by": actor.email}
    names = ", ".join(r["name"] for r in roles)
    super_admin = any(r["builtin_key"] == access.SUPER_ADMIN for r in roles)
    outcome = approvals.request("staff.super_admin" if super_admin else "staff.create",
                                {**payload, "kind": "create"},
                                f"Invite {email} ({payload['fullname'] or 'no name'}) as staff with role(s): {names}",
                                actor, target=f"staff-email:{email}", client=client)
    return _outcome(outcome)


def exec_create(payload: dict, actor_label: str) -> dict:
    if staff_service.get_staff_by_email(payload["email"]):
        raise StaffAdminError("A staff member with this email already exists", 409)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "insert into staff_users (email, fullname, status, created_by) values (%s, %s, 'invited', %s) "
            "returning id::text", (payload["email"], payload["fullname"], actor_label)).fetchone()
        for role_id in payload["role_ids"]:
            conn.execute("insert into staff_user_roles (staff_id, role_id, granted_by) values (%s, %s, %s)",
                         (row["id"], role_id, actor_label))
    staff = staff_service.get_staff(row["id"])
    link = staff_service.issue_link(staff, "invite", actor_label)
    sent = staff_service.send_invite(staff, link, payload.get("invited_by") or actor_label)
    staff_service.audit("staff.invited", actor_email=payload.get("invited_by"), target=f"staff:{row['id']}",
                        details={"email": payload["email"], "role_ids": payload["role_ids"], "by": actor_label,
                                 "email_sent": sent})
    return {"staff_id": row["id"], "email_sent": sent}


def exec_set_roles(payload: dict, actor_label: str) -> dict:
    if payload.get("kind") == "create":
        return exec_create(payload, actor_label)
    staff_id = payload["staff_id"]
    if not staff_service.get_staff(staff_id):
        raise StaffAdminError("Staff member not found", 404)
    roles = _roles_for(payload["role_ids"])
    super_role = fetch_one("select id::text from staff_roles where builtin_key = 'super_admin'")["id"]
    will_be_super = any(r["id"] == super_role for r in roles)
    if not will_be_super and staff_id in access.active_super_admin_ids() and len(access.active_super_admin_ids()) <= 1:
        raise StaffAdminError("This is the last active Super admin; make someone else Super admin first", 409)
    with connection() as conn, conn.transaction():
        conn.execute("delete from staff_user_roles where staff_id = %s and not (role_id::text = any(%s))",
                     (staff_id, [r["id"] for r in roles]))
        for r in roles:
            conn.execute("insert into staff_user_roles (staff_id, role_id, granted_by) values (%s, %s, %s) "
                         "on conflict do nothing", (staff_id, r["id"], actor_label))
    return {"staff_id": staff_id, "roles": [r["name"] for r in roles]}


def set_roles(actor: StaffActor, staff_id: str, role_ids: list[str], client: ClientInfo | None = None) -> dict:
    target = _target(actor, staff_id)
    roles = _roles_for(role_ids)
    if not roles:
        raise StaffAdminError("Keep at least one role. To remove all access, disable the account.", 422)
    current = {r["id"]: r for r in access.staff_roles(staff_id)}
    wanted = {r["id"]: r for r in roles}
    added = [wanted[i] for i in wanted if i not in current]
    removed = [current[i] for i in current if i not in wanted]
    if not added and not removed:
        return {"unchanged": True}
    _check_can_grant(actor, added)
    touches_super = any(r["builtin_key"] == access.SUPER_ADMIN for r in added + removed)
    if (any(r["builtin_key"] == access.SUPER_ADMIN for r in removed) and staff_id in access.active_super_admin_ids()
            and len(access.active_super_admin_ids()) <= 1):
        raise StaffAdminError("This is the last active Super admin; make someone else Super admin first", 409)
    parts = []
    if added:
        parts.append("add " + ", ".join(r["name"] for r in added))
    if removed:
        parts.append("remove " + ", ".join(r["name"] for r in removed))
    outcome = approvals.request(
        "staff.super_admin" if touches_super else "staff.set_roles",
        {"staff_id": staff_id, "role_ids": list(wanted)},
        f"Change roles of {target['email']}: {'; '.join(parts)}",
        actor, target=f"staff:{staff_id}", beneficiaries=[staff_id] if added else [], client=client,
    )
    return _outcome(outcome)


def disable(actor: StaffActor, staff_id: str, client: ClientInfo | None = None) -> dict:
    target = _target(actor, staff_id)
    if target["status"] == "disabled":
        raise StaffAdminError("Already disabled", 409)
    if staff_id in access.active_super_admin_ids() and len(access.active_super_admin_ids()) <= 1:
        raise StaffAdminError("This is the last active Super admin and can't be disabled", 409)
    outcome = approvals.request("staff.disable", {"staff_id": staff_id},
                                f"Disable {target['email']}: they are signed out and can't sign in",
                                actor, target=f"staff:{staff_id}", client=client)
    return _outcome(outcome)


def exec_disable(payload: dict, actor_label: str) -> dict:
    staff_id = payload["staff_id"]
    supers = access.active_super_admin_ids()
    if staff_id in supers and len(supers) <= 1:
        raise StaffAdminError("This is the last active Super admin and can't be disabled", 409)
    row = fetch_one("update staff_users set status = 'disabled', updated_at = now() where id = %s returning id::text",
                    (staff_id,))
    if not row:
        raise StaffAdminError("Staff member not found", 404)
    signed_out = staff_service.revoke_all_sessions(staff_id, "disabled")
    staff_service.revoke_links(staff_id)
    return {"staff_id": staff_id, "signed_out": signed_out}


def enable(actor: StaffActor, staff_id: str, client: ClientInfo | None = None) -> dict:
    target = _target(actor, staff_id)
    if target["status"] != "disabled":
        raise StaffAdminError("This account isn't disabled", 409)
    outcome = approvals.request("staff.enable", {"staff_id": staff_id},
                                f"Enable {target['email']} again with their current roles",
                                actor, target=f"staff:{staff_id}", beneficiaries=[staff_id], client=client)
    return _outcome(outcome)


def exec_enable(payload: dict, actor_label: str) -> dict:
    row = fetch_one(
        """
        update staff_users set status = case when password_hash is null then 'invited' else 'active' end,
          updated_at = now()
        where id = %s and status = 'disabled' returning id::text, status
        """,
        (payload["staff_id"],),
    )
    if not row:
        raise StaffAdminError("This account isn't disabled any more", 409)
    return {"staff_id": row["id"], "status": row["status"]}


def update_profile(actor: StaffActor, staff_id: str, fullname: str, client: ClientInfo | None = None) -> dict:
    target = _target(actor, staff_id, allow_self=True)
    fetch_one("update staff_users set fullname = %s, updated_at = now() where id = %s returning id",
              ((fullname or "").strip()[:120], staff_id))
    staff_service.audit("staff.renamed", actor=actor, target=f"staff:{staff_id}", client=client,
                        details={"before": target["fullname"], "after": (fullname or "").strip()[:120]})
    return get_staff(staff_id)


def send_link(actor: StaffActor, staff_id: str, kind: str, client: ClientInfo | None = None) -> dict:
    """Resend an invitation, or send a password reset link. The link is shown only when email isn't set up."""
    target = _target(actor, staff_id)
    if kind == "invite" and target["status"] != "invited":
        raise StaffAdminError("This person already accepted their invitation; send a password reset instead", 409)
    if kind == "reset" and target["status"] != "active":
        raise StaffAdminError("Only active accounts can reset their password", 409)
    link = staff_service.issue_link(target, kind, actor.email)
    sent = (staff_service.send_invite(target, link, actor.email) if kind == "invite"
            else staff_service.send_reset(target, link))
    staff_service.audit("staff.invite_resent" if kind == "invite" else "staff.reset_link_sent", actor=actor,
                        target=f"staff:{staff_id}", client=client, details={"email_sent": sent})
    return {"email_sent": sent, "link": None if sent else link,
            "expires_in_minutes": staff_service.INVITE_TTL_HOURS * 60 if kind == "invite" else staff_service.RESET_TTL_MINUTES}


def revoke_invite(actor: StaffActor, staff_id: str, client: ClientInfo | None = None) -> dict:
    target = _target(actor, staff_id)
    if target["status"] != "invited":
        raise StaffAdminError("There is no open invitation", 409)
    count = staff_service.revoke_links(staff_id, "invite")
    staff_service.audit("staff.invite_revoked", actor=actor, target=f"staff:{staff_id}", client=client)
    return {"revoked": count}


def sign_out(actor: StaffActor, staff_id: str, client: ClientInfo | None = None) -> dict:
    _target(actor, staff_id)
    count = staff_service.revoke_all_sessions(staff_id, "revoked_by_staff_admin")
    staff_service.audit("staff.signed_out", actor=actor, target=f"staff:{staff_id}", client=client,
                        details={"sessions": count})
    return {"signed_out": count}
