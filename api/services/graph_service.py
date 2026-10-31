"""Compliance graph queries for path generation (graph tables in Postgres, see services.graph_store)."""

from __future__ import annotations

import re
from typing import Any

from models.compliance_nodes import ServiceNode
from services import graph_store
from services.db import fetch_all, fetch_one


# Seed templates used +251 11 000 000x as stand-in numbers. Never show those as real contacts.
_PLACEHOLDER_PHONE = re.compile(r"^(251)?0?11000000\d$")


def real_phones(phones: list[str] | None) -> list[str]:
    return [p for p in phones or [] if p and not _PLACEHOLDER_PHONE.match(re.sub(r"\D", "", p))]


# Offices that serve residents by where they live: the right desk is their own woreda office
_RESIDENT_DOCS = {"birth_certificate", "kebele_id"}


def _office_note(doc_id: str, sub_label: str, has_phone: bool) -> str | None:
    if doc_id in _RESIDENT_DOCS:
        return (f"Go to the woreda office where you are registered as a resident in {sub_label}. "
                f"If you are not sure which one, ask at the {sub_label} sub-city administration.")
    if not has_phone:
        return f"We do not have a verified phone for this office yet. Confirm the address at the {sub_label} sub-city administration before you go."
    return None


def graph_is_seeded() -> bool:
    return bool(fetch_one("select exists (select 1 from graph_nodes where label = 'Service') as seeded")["seeded"])


def list_services_from_graph() -> list[dict]:
    rows = [s for s in graph_store.find_nodes("Service") if s.get("is_active") in (None, True)]
    rows.sort(key=lambda s: (s.get("sort_order") is None, s.get("sort_order") or 0, s.get("name") or ""))
    return [
        {"id": s["id"], "name": s.get("name"), "description": s.get("description"),
         "category": s.get("category"), "sort_order": s.get("sort_order")}
        for s in rows
    ]


def _linked_ids(label: str, id: str, type: str, target_label: str) -> list[str]:
    return [n["id"] for n in graph_store.neighbors(label, id, type, "out") if n["label"] == target_label]


def _requires_pairs(ids: list[str]) -> list[dict]:
    """REQUIRES links between documents: prereq (the source) comes before dep (the target)."""
    return fetch_all(
        """
        select src_id as prereq, dst_id as dep from graph_edges
        where type = 'REQUIRES' and src_label = 'Document' and dst_label = 'Document'
          and src_id = any(%(ids)s) and dst_id = any(%(ids)s)
        order by src_id, dst_id
        """,
        {"ids": list(ids)},
    )


def _topo_sort_documents(doc_ids: list[str], requires_pairs: list[tuple[str, str]]) -> list[str]:
    """Order documents: prerequisite before dependent (requires: prereq -> dependent)."""
    ids = set(doc_ids)
    preds: dict[str, set[str]] = {d: set() for d in ids}
    succ: dict[str, set[str]] = {d: set() for d in ids}
    for prereq, dep in requires_pairs:
        if prereq in ids and dep in ids:
            preds[dep].add(prereq)
            succ[prereq].add(dep)

    ordered: list[str] = []
    ready = [d for d in ids if not preds[d]]
    while ready:
        ready.sort()
        n = ready.pop(0)
        ordered.append(n)
        for m in list(succ[n]):
            preds[m].discard(n)
            if not preds[m]:
                ready.append(m)

    for d in ids:
        if d not in ordered:
            ordered.append(d)
    return ordered


def get_path_document_ids(
    goal: str,
    documents_held: list[str],
    industry: str | None = None,
) -> list[str] | None:
    """
    Return ordered document ids from prerequisites through target for the service.
    Excludes documents already held unless needed as anchors.
    """
    targets = _linked_ids("Service", goal, "TARGETS", "Document")
    if not targets:
        return None

    target_id = targets[0]

    # Every document with a chain of REQUIRES links to the target (cycles are safe)
    doc_ids = {i for label, i in graph_store.ancestors_via("REQUIRES", "Document", target_id) if label == "Document"}
    doc_ids.add(target_id)

    if industry:
        doc_ids.update(_linked_ids("Sector", industry, "SECTOR_EXTRA", "Document"))

    pairs = [(r["prereq"], r["dep"]) for r in _requires_pairs(list(doc_ids))]

    ordered = _topo_sort_documents(list(doc_ids), pairs)
    held = set(documents_held)

    # Only steps the user still needs (skip documents they already hold)
    steps = [d for d in ordered if d not in held]
    if not steps and target_id not in held:
        steps = [target_id]
    return steps if steps else [target_id]


_MAIN_OFFICES = ("ics_main", "motri_main", "nbe_main")


def _issuing_office(doc_id: str, sub_city: str) -> dict | None:
    """The office in the citizen's sub-city that issues the document, else the main federal office."""
    offices = fetch_all(
        """
        select o.id, o.props,
               exists (select 1 from graph_edges l
                       where l.type = 'LOCATED_IN' and l.src_label = 'Office' and l.src_id = o.id
                         and l.dst_label = 'SubCity' and l.dst_id = %(sub_city)s) as local
        from graph_edges e join graph_nodes o on o.label = e.dst_label and o.id = e.dst_id
        where e.type = 'ISSUED_BY' and e.src_label = 'Document' and e.src_id = %(doc_id)s
          and e.dst_label = 'Office'
        order by o.id
        """,
        {"doc_id": doc_id, "sub_city": sub_city},
    )
    for o in offices:
        if o["local"]:
            return o["props"]
    for o in offices:
        if o["id"] in _MAIN_OFFICES:
            return o["props"]
    return None


def get_document_with_office(doc_id: str, sub_city: str, sub_label: str | None = None) -> dict | None:
    d = graph_store.get_node("Document", doc_id)
    if d is None:
        return None
    o = _issuing_office(doc_id, sub_city)

    office = None
    if o and o.get("id"):
        sub_label = sub_label or sub_city.replace("_", " ").title()
        local = o["id"] not in _MAIN_OFFICES
        phones = real_phones(o.get("phones"))
        office = {
            "name": (o.get("name") or "").replace("{sub_city}", sub_label),
            "parentInstitution": o.get("parent_institution") or "",
            "subCity": sub_label,
            "address": (o.get("address_detail") or "").replace("{sub_city}", sub_label),
            "landmark": o.get("landmark"),
            "latitude": o.get("latitude"),
            "longitude": o.get("longitude"),
            "phones": phones,
            "workingHours": o.get("working_hours") or "Mon–Fri 08:30–17:00 (EAT)",
        }
        note = _office_note(d.get("id"), sub_label, bool(phones)) if local else None
        if note:
            office["note"] = note

    return {
        "id": d.get("id"),
        "name": d.get("name"),
        "name_am": d.get("name_am"),
        "issuing_authority": d.get("issuing_authority"),
        "form_code": d.get("form_code"),
        "fee_etb": d.get("fee_etb"),
        "avg_days": d.get("avg_processing_days"),
        "legal_basis": d.get("legal_basis"),
        "required_inputs": d.get("required_input_labels") or [],
        "rejection_reasons": d.get("rejection_reasons") or [],
        "source_url": d.get("source_url"),
        "sector_specific": d.get("sector_specific"),
        "stale": d.get("stale"),
        "office": office,
    }


def get_prerequisites_many(doc_ids: list[str]) -> dict[str, list[str]]:
    """Direct prerequisites of several documents in one query."""
    found: dict[str, list[str]] = {d: [] for d in doc_ids}
    for r in fetch_all(
        """
        select dst_id as id, array_agg(src_id order by src_id) as pres from graph_edges
        where type = 'REQUIRES' and src_label = 'Document' and dst_label = 'Document' and dst_id = any(%s)
        group by dst_id
        """,
        (list(doc_ids),),
    ):
        found[r["id"]] = r["pres"]
    return found


def get_prerequisites(doc_id: str) -> list[str]:
    return [n["id"] for n in graph_store.neighbors("Document", doc_id, "REQUIRES", "in") if n["label"] == "Document"]


def build_roadmap_from_graph(
    goal: str,
    sub_city: str,
    documents_held: list[str],
    industry: str | None = None,
) -> dict | None:
    service = ServiceNode.match(goal)
    if not service:
        return None

    doc_ids = get_path_document_ids(goal, documents_held, industry)
    if not doc_ids:
        return None

    held = set(documents_held)
    sub_label = _sub_city_label(sub_city)
    steps: list[dict] = []

    prereqs_by_doc = get_prerequisites_many(doc_ids)
    for order, doc_id in enumerate(doc_ids, start=1):
        detail = get_document_with_office(doc_id, sub_city, sub_label)
        if not detail:
            continue

        prereqs = prereqs_by_doc.get(doc_id, [])
        if doc_id in held:
            status = "completed"
        else:
            status = "pending"

        avg = detail.get("avg_days")
        est = f"{avg}–{avg + 3}" if avg else "5–15"

        step: dict[str, Any] = {
            "id": doc_id,
            "order": order,
            "title": detail["name"],
            "titleAm": detail.get("name_am"),
            "issuingAuthority": detail.get("issuing_authority") or "",
            "formCode": detail.get("form_code"),
            "feeEtb": detail.get("fee_etb"),
            "paymentMethods": ["cash"],
            "estimatedDays": est,
            "legalBasis": detail.get("legal_basis"),
            "sourceUrl": detail.get("source_url"),
            "status": status,
            "sectorSpecific": detail.get("sector_specific") or False,
            "requiredInputs": detail.get("required_inputs") or [],
            "prerequisiteIds": prereqs,
            "rejectionReasons": detail.get("rejection_reasons") or [],
        }
        if detail.get("office"):
            step["office"] = detail["office"]
        steps.append(step)

    active_set = False
    for step in steps:
        if step["status"] != "pending":
            continue
        prereqs = step.get("prerequisiteIds") or []
        ready = all(
            p in held or any(s["id"] == p and s["status"] == "completed" for s in steps)
            for p in prereqs
        )
        if ready and not active_set:
            step["status"] = "active"
            active_set = True
        elif not ready:
            step["status"] = "blocked"

    if not steps:
        return None

    remaining = [s for s in steps if s["status"] != "completed"]
    total_min = sum(
        int(str(s["estimatedDays"]).split("–")[0].replace("~", ""))
        for s in remaining
        if s.get("estimatedDays")
    ) or 0

    category = "personal" if service.category in ("identity", "travel") else "business"

    return {
        "request": {
            "goal": goal,
            "goalLabel": service.name,
            "category": category,
            "subCity": sub_city,
            "subCityLabel": sub_label,
            "industry": industry,
            "documentsHeld": list(documents_held),
        },
        "steps": steps,
        "totalEstimatedDays": (
            f"~{total_min}+ business days remaining" if total_min else "All steps complete"
        ),
        "trackedCompleted": list(documents_held),
    }


def _sub_city_label(sub_city: str) -> str:
    sc = graph_store.get_node("SubCity", sub_city)
    if sc and sc.get("label"):
        return sc["label"]
    return sub_city.replace("_", " ").title()


def list_offices(sub_city: str | None = None) -> list[dict]:
    return [{**o, "phones": real_phones(o.get("phones"))} for o in _list_offices(sub_city)]


_OFFICE_FIELDS = ("id", "name", "parent_institution", "address_detail", "landmark", "latitude", "longitude",
                  "phones", "working_hours", "documents_issued")


def _list_offices(sub_city: str | None) -> list[dict]:
    """Offices with the label of the sub-city each is in (one row per sub-city link)."""
    rows = fetch_all(
        f"""
        select o.props, sc.props->>'label' as sub_city_label
        from graph_nodes o
        {"join" if sub_city else "left join"} graph_edges l
          on l.type = 'LOCATED_IN' and l.src_label = 'Office' and l.src_id = o.id and l.dst_label = 'SubCity'
          {"and l.dst_id = %(sub_city)s" if sub_city else ""}
        left join graph_nodes sc on sc.label = l.dst_label and sc.id = l.dst_id
        where o.label = 'Office'
        order by o.props->>'name', o.id
        """,
        {"sub_city": sub_city},
    )
    return [{**{k: r["props"].get(k) for k in _OFFICE_FIELDS}, "sub_city_label": r["sub_city_label"]} for r in rows]
