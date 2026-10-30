"""Public reads: live organizations and services, service paths and eligibility checks."""

from __future__ import annotations

import logging
from typing import Any

from services.db import fetch_all, fetch_one
from .analytics import record_stat
from .branches import hours_text, list_branches
from .helpers import PUBLIC_ORG_COLUMNS, OrgError, _plain
from .review import promote_due_changes
from .services_edit import _confirmation

log = logging.getLogger(__name__)


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
