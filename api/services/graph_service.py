"""Neo4j graph queries for compliance path generation."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from neontology import GraphConnection

from models.compliance_nodes import DocumentNode, ServiceNode


def _query_rows(cypher: str, params: dict | None = None) -> list[dict]:
    """Neo4j driver rows as plain dicts (neontology .records is often empty)."""
    gc = GraphConnection()
    result = gc.evaluate_query(cypher, params or {})
    return [dict(rec) for rec in (result.records_raw or [])]


def graph_is_seeded() -> bool:
    gc = GraphConnection()
    result = gc.evaluate_query_single(
        "MATCH (s:Service) RETURN count(s) AS c LIMIT 1"
    )
    return bool(result and result > 0)


def list_services_from_graph() -> list[dict]:
    return _query_rows(
        """
        MATCH (s:Service)
        WHERE s.is_active IS NULL OR s.is_active = true
        RETURN s.id AS id, s.name AS name, s.description AS description,
               s.category AS category, s.sort_order AS sort_order
        ORDER BY s.sort_order, s.name
        """
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
    targets = _query_rows(
        """
        MATCH (s:Service {id: $goal})-[:TARGETS]->(end:Document)
        RETURN end.id AS target_id
        """,
        {"goal": goal},
    )
    if not targets:
        return None

    target_id = targets[0]["target_id"]

    path_rows = _query_rows(
        """
        MATCH (s:Service {id: $goal})-[:TARGETS]->(end:Document {id: $target_id})
        MATCH (d:Document)-[:REQUIRES*]->(end)
        RETURN DISTINCT d.id AS id
        """,
        {"goal": goal, "target_id": target_id},
    )
    doc_ids = {r["id"] for r in path_rows}
    doc_ids.add(target_id)

    if industry:
        for r in _query_rows(
            """
            MATCH (sec:Sector {id: $industry})-[:SECTOR_EXTRA]->(d:Document)
            RETURN DISTINCT d.id AS id
            """,
            {"industry": industry},
        ):
            doc_ids.add(r["id"])

    req_rows = _query_rows(
        """
        MATCH (a:Document)-[r:REQUIRES]->(b:Document)
        WHERE a.id IN $ids AND b.id IN $ids
        RETURN a.id AS prereq, b.id AS dep
        """,
        {"ids": list(doc_ids)},
    )
    pairs = [(r["prereq"], r["dep"]) for r in req_rows]

    ordered = _topo_sort_documents(list(doc_ids), pairs)
    held = set(documents_held)

    # Only steps the user still needs (skip documents they already hold)
    steps = [d for d in ordered if d not in held]
    if not steps and target_id not in held:
        steps = [target_id]
    return steps if steps else [target_id]


def get_document_with_office(doc_id: str, sub_city: str) -> dict | None:
    rows = _query_rows(
        """
        MATCH (d:Document {id: $doc_id})
        OPTIONAL MATCH (d)-[:ISSUED_BY]->(o:Office)-[:LOCATED_IN]->(sc:SubCity {id: $sub_city})
        WITH d, o AS office_subcity
        OPTIONAL MATCH (d)-[:ISSUED_BY]->(oMain:Office)
        WHERE oMain.id IN ['ics_main', 'motri_main', 'nbe_main']
        WITH d, coalesce(office_subcity, oMain) AS o
        RETURN d.id AS id, d.name AS name, d.name_am AS name_am,
               d.issuing_authority AS issuing_authority, d.form_code AS form_code,
               d.fee_etb AS fee_etb, d.avg_processing_days AS avg_days,
               d.legal_basis AS legal_basis, d.required_input_labels AS required_inputs,
               d.rejection_reasons AS rejection_reasons, d.source_url AS source_url,
               d.sector_specific AS sector_specific, d.stale AS stale,
               o.id AS office_id, o.name AS office_name,
               o.parent_institution AS office_parent, o.address_detail AS office_address,
               o.landmark AS office_landmark, o.latitude AS office_lat,
               o.longitude AS office_lng, o.phones AS office_phones,
               o.working_hours AS office_hours
        LIMIT 1
        """,
        {"doc_id": doc_id, "sub_city": sub_city},
    )
    if not rows:
        d = DocumentNode.match(doc_id)
        if not d:
            return None
        return {
            "id": d.id,
            "name": d.name,
            "name_am": d.name_am,
            "issuing_authority": d.issuing_authority,
            "form_code": d.form_code,
            "fee_etb": d.fee_etb,
            "avg_days": d.avg_processing_days,
            "legal_basis": d.legal_basis,
            "required_inputs": d.required_input_labels or [],
            "rejection_reasons": d.rejection_reasons or [],
            "source_url": d.source_url,
            "sector_specific": d.sector_specific,
            "stale": d.stale,
            "office": None,
        }

    row = rows[0]

    office = None
    if row.get("office_id"):
        sub_label = sub_city.replace("_", " ").title()
        office = {
            "name": (row.get("office_name") or "").replace("{sub_city}", sub_label),
            "parentInstitution": row.get("office_parent") or "",
            "subCity": sub_label,
            "address": (row.get("office_address") or "").replace("{sub_city}", sub_label),
            "landmark": row.get("office_landmark"),
            "latitude": row.get("office_lat"),
            "longitude": row.get("office_lng"),
            "phones": row.get("office_phones") or [],
            "workingHours": row.get("office_hours") or "Mon–Fri 08:30–17:00 (EAT)",
        }

    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "name_am": row.get("name_am"),
        "issuing_authority": row.get("issuing_authority"),
        "form_code": row.get("form_code"),
        "fee_etb": row.get("fee_etb"),
        "avg_days": row.get("avg_days"),
        "legal_basis": row.get("legal_basis"),
        "required_inputs": row.get("required_inputs") or [],
        "rejection_reasons": row.get("rejection_reasons") or [],
        "source_url": row.get("source_url"),
        "sector_specific": row.get("sector_specific"),
        "stale": row.get("stale"),
        "office": office,
    }


def get_prerequisites(doc_id: str) -> list[str]:
    return [r["id"] for r in _query_rows(
        """
        MATCH (pre:Document)-[:REQUIRES]->(d:Document {id: $doc_id})
        RETURN pre.id AS id
        """,
        {"doc_id": doc_id},
    )]


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

    for order, doc_id in enumerate(doc_ids, start=1):
        detail = get_document_with_office(doc_id, sub_city)
        if not detail:
            continue

        prereqs = get_prerequisites(doc_id)
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
    rows = _query_rows(
        "MATCH (sc:SubCity {id: $id}) RETURN sc.label AS label",
        {"id": sub_city},
    )
    if rows:
        return rows[0]["label"]
    return sub_city.replace("_", " ").title()


def list_offices(sub_city: str | None = None) -> list[dict]:
    if sub_city:
        return _query_rows(
            """
            MATCH (o:Office)-[:LOCATED_IN]->(sc:SubCity {id: $sub_city})
            RETURN o.id AS id, o.name AS name, o.parent_institution AS parent_institution,
                   o.address_detail AS address_detail, o.landmark AS landmark,
                   o.latitude AS latitude, o.longitude AS longitude,
                   o.phones AS phones, o.working_hours AS working_hours,
                   o.documents_issued AS documents_issued, sc.label AS sub_city_label
            ORDER BY o.name
            """,
            {"sub_city": sub_city},
        )
    return _query_rows(
        """
        MATCH (o:Office)
        OPTIONAL MATCH (o)-[:LOCATED_IN]->(sc:SubCity)
        RETURN o.id AS id, o.name AS name, o.parent_institution AS parent_institution,
               o.address_detail AS address_detail, o.landmark AS landmark,
               o.latitude AS latitude, o.longitude AS longitude,
               o.phones AS phones, o.working_hours AS working_hours,
               o.documents_issued AS documents_issued, sc.label AS sub_city_label
        ORDER BY o.name
        """
    )
