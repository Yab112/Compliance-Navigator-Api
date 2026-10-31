"""Staff review of organizations and service submissions, and putting approved changes live."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any

from services.db import Jsonb, connection, fetch_all, fetch_one
from services import platform_settings
from .branches import list_branches
from .graph_sync import remove_service_from_graph, sync_service_to_graph
from .helpers import ADMIN_ORG_COLUMNS, MEMBER_ORG_COLUMNS, NOTE_REQUIRED, ORG_ACTIONS, OrgError, _log, _plain
from .orgs import member_org
from .services_edit import _completeness_by_service, completeness, list_org_services

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- review (staff)


def review_org(org_id: str, action: str, *, actor: str, note: str | None,
               catalog_institution_id: str | None = None) -> dict:
    allowed_from, new_status = ORG_ACTIONS[action]
    if action in NOTE_REQUIRED and not (note or "").strip():
        raise OrgError("Add a note explaining the decision")
    with connection() as conn, conn.transaction():
        org = conn.execute("select status, authorization_letter_key from organizations where id = %s for update",
                           (org_id,)).fetchone()
        if not org:
            raise OrgError("Organization not found", 404)
        if org["status"] not in allowed_from:
            raise OrgError(f"Can't {action} an organization that is {org['status']}", 409)
        # The letter is the proof that the representative may speak for the organization
        if new_status == "verified" and not org["authorization_letter_key"]:
            raise OrgError("This organization has not uploaded an authorization letter. Ask for one before verifying.", 409)
        conn.execute(
            """
            update organizations set status = %s, verification_note = %s, reviewed_by = %s, reviewed_at = now(),
              catalog_institution_id = coalesce(%s, catalog_institution_id), updated_at = now()
            where id = %s
            """,
            (new_status, note, actor, catalog_institution_id, org_id),
        )
        _log(conn, action, org_id=org_id, actor=actor, note=note)
        live = conn.execute("select id::text from org_services where org_id = %s and published_snapshot is not null "
                            "and status <> 'archived'", (org_id,)).fetchall()
        for s in live:
            if new_status == "verified":
                sync_service_to_graph(s["id"], conn)
            elif new_status == "suspended":
                remove_service_from_graph(s["id"], conn)
    title, body = ORG_DECISION_MESSAGES[action]
    _notify_members(org_id, kind=f"org_{action}", title=title, body=(f"{body} Note from our team: {note}" if note else body))
    return admin_org(org_id)


ORG_DECISION_MESSAGES = {
    "verify": ("Your organization is verified",
               "Staff checked your authorization letter. Services you send for review can now be published."),
    "reject": ("Your organization registration was not accepted",
               "Read the note, fix what it asks for and contact us if you have questions."),
    "suspend": ("Your organization is suspended",
                "Your services are hidden from the public until staff reinstate the organization."),
    "reinstate": ("Your organization is active again", "Your published services are visible to the public again."),
}


def _notify_members(org_id: str, *, kind: str, title: str, body: str, link: str | None = None) -> None:
    """Tell every member of the organization about a staff decision. Never blocks the decision."""
    try:
        from services import notifications

        members = fetch_all("select user_id::text from organization_members where org_id = %s and accepted "
                            "and user_id is not null", (org_id,))
        notifications.notify([m["user_id"] for m in members], kind=kind, title=title, body=body,
                             link=link or f"/org/{org_id}")
    except Exception:
        log.exception("Could not notify members of organization %s", org_id)


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
    days = platform_settings.get_int("org_confirm_every_days")
    items = fetch_all(
        f"""
        select {MEMBER_ORG_COLUMNS}, count(*) over () as total_count,
          (select count(*) from org_services s where s.org_id = o.id and s.published_snapshot is not null
             and s.status <> 'archived') as live_services,
          (select count(*) from org_services s where s.org_id = o.id and s.published_snapshot is not null
             and s.status <> 'archived' and (s.last_confirmed_at is null
             or s.last_confirmed_at < now() - make_interval(days => %s))) as services_due,
          (select count(*) from feedback_flags f where f.org_id = o.id and f.status = 'open') as open_reports
        from organizations o where {clause} order by o.created_at desc limit %s offset %s
        """,
        [days, *params, limit, offset],
    )
    if items:
        total = items[0]["total_count"]
    else:  # past the last page, so the window count is missing
        total = fetch_one(f"select count(*) as c from organizations o where {clause}", params)["c"]
    by_org: dict[str, list[int]] = {}
    for c in _completeness_by_service([o["id"] for o in items]).values():
        if not c["archived"]:  # archived services don't count towards "data filled"
            by_org.setdefault(c["org_id"], []).append(c["completeness"]["score"])
    for org in items:
        org.pop("total_count", None)
        mine = by_org.get(org["id"])
        org["completeness"] = round(sum(mine) / len(mine)) if mine else None
    return {"total": total, "items": items, "confirm_every_days": days}


SUBMISSION_FILTER = """
  (%(status)s = 'all' or r.status = %(status)s)
  and (%(org_id)s::uuid is null or s.org_id = %(org_id)s::uuid)
  and (%(q)s::text is null or s.name ilike %(q)s or o.name ilike %(q)s or r.change_summary ilike %(q)s)
"""


def _submission_params(status: str, org_id: str | None, q: str | None) -> dict:
    return {"status": status, "org_id": org_id, "q": f"%{q.strip()}%" if q and q.strip() else None}


EXPORT_LIMIT = 5000
EXPORT_COLUMNS = (
    ("name", "Name"), ("name_am", "Name (Amharic)"), ("org_type", "Type"), ("status", "Status"),
    ("representative_name", "Representative"), ("representative_title", "Representative title"),
    ("official_email", "Official email"), ("phone", "Public phone"), ("email", "Public email"),
    ("website", "Website"), ("region", "Region"), ("sub_city", "Sub-city"),
    ("has_authorization_letter", "Authorization letter"), ("live_services", "Live services"),
    ("completeness", "Data filled (%)"), ("services_due", "Services not confirmed"),
    ("open_reports", "Open reports"), ("created_at", "Registered"), ("reviewed_at", "Last decision"),
)


def _csv_cell(value: Any) -> str:
    """Spreadsheet-safe text: a cell starting with = + - @ (or a tab or return) is a formula to Excel."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = value.isoformat() if isinstance(value, (datetime, date)) else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def orgs_admin_csv(status: str | None, q: str | None) -> str:
    import csv
    import io

    rows = list_orgs_admin(status, q, EXPORT_LIMIT, 0)["items"]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([label for _, label in EXPORT_COLUMNS])
    for r in rows:
        writer.writerow([_csv_cell(r.get(key)) for key, _ in EXPORT_COLUMNS])
    return out.getvalue()


def count_submissions(status: str = "pending", org_id: str | None = None, q: str | None = None) -> int:
    return fetch_one(
        "select count(*) as c from org_service_revisions r join org_services s on s.id = r.service_id "
        f"join organizations o on o.id = s.org_id where {SUBMISSION_FILTER}",
        _submission_params(status, org_id, q),
    )["c"]


def list_submissions(status: str = "pending", limit: int = 50, offset: int = 0, org_id: str | None = None,
                     q: str | None = None) -> list[dict]:
    return fetch_all(
        f"""
        select r.id::text, r.status, r.submitted_by, r.created_at, r.reviewed_at, r.admin_note,
               r.change_summary, r.effective_at,
               s.id::text as service_id, s.name as service_name, (s.published_snapshot is not null) as is_update,
               o.id::text as org_id, o.name as org_name, o.status as org_status
        from org_service_revisions r
        join org_services s on s.id = r.service_id
        join organizations o on o.id = s.org_id
        where {SUBMISSION_FILTER}
        order by r.created_at desc limit %(limit)s offset %(offset)s
        """,
        {**_submission_params(status, org_id, q), "limit": limit, "offset": offset},
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
    # Names for the ids inside the snapshots, so staff read "Bole branch" instead of a uuid
    row["branch_names"] = {b["id"]: b["name"] for b in fetch_all(
        "select id::text, name from organization_branches where org_id = %s", (row["org_id"],))}
    service_ids = set()
    for snap in (row["snapshot"], row["published_snapshot"] or {}):
        service_ids.update(r.get("issuing_service_id") for r in snap.get("requirements") or [])
        service_ids.add(snap.get("renewal_service_id"))
    service_ids = [i for i in service_ids if i]
    row["service_names"] = {s["id"]: f"{s['name']} ({s['org_name']})" for s in fetch_all(
        "select s.id::text, s.name, o.name as org_name from org_services s join organizations o on o.id = s.org_id "
        "where s.id::text = any(%s)", (service_ids,))} if service_ids else {}
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
            sync_service_to_graph(rev["service_id"], conn)
    if went_live:
        _notify_change(rev, upcoming=False)
    if scheduled:
        _notify_change(rev, upcoming=True)
    name = rev["snapshot"].get("name") or "Your service"
    if action == "publish":
        title = (f"Approved: {name} goes live on {rev['effective_at'].isoformat()}" if scheduled
                 else f"Published: {name} is now live")
        body = "Staff approved your submission." + (f" Note from our team: {note}" if note else "")
    else:
        title, body = f"Changes requested: {name}", f"Staff asked for changes before publishing: {note}"
    _notify_members(rev["org_id"], kind="service_published" if action == "publish" else "service_changes_requested",
                    title=title, body=body, link=f"/org/{rev['org_id']}/services/{rev['service_id']}")
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
            sync_service_to_graph(rev["service_id"], conn)
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
             and (last_confirmed_at is null or last_confirmed_at < now() - make_interval(days => %s))) as services_due,
          (select count(*) from feedback_flags where org_id is not null and status = 'open') as open_reports
        """,
        (platform_settings.get_int("org_confirm_every_days"),),
    )
