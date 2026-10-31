"""Graph maintenance for the admin dashboard: MESOB sync, stats, stale checks, editing."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from services import catalog_service, graph_store
from services.db import connection, fetch_all, fetch_one

# Properties an admin may edit on a Document node from the dashboard
EDITABLE_DOCUMENT_FIELDS = {
    "name", "name_am", "issuing_authority", "form_code", "fee_etb",
    "avg_processing_days", "legal_basis", "source_url",
    "required_input_labels", "rejection_reasons",
}


def sync_catalog_to_graph() -> dict:
    """Mirror the MESOB snapshot into the graph and link roadmap documents to it, in one transaction."""
    catalog = catalog_service.load_catalog()
    today = date.today().isoformat()

    institutions = [
        {
            "id": i["id"], "name": i.get("name"), "name_am": i.get("name_am"),
            "short_name": i.get("short_name"), "logo_url": i.get("logo_url"),
            "service_count": i.get("service_count", 0),
            "at_mesob": True, "scrape_method": "mesob_api",
        }
        for i in catalog["institutions"]
    ]
    services = [
        {
            "id": s["id"], "source_id": s.get("source_id"), "language": s["language"],
            "name": s["name"], "institution_id": s["institution_id"],
            "required_documents": s.get("required_documents") or [],
            "processing_time_text": s.get("processing_time_text"),
            "processing_minutes": s.get("processing_minutes"),
            "fee_text": s.get("fee_text"), "fee_etb_min": s.get("fee_etb_min"),
            "fee_etb_max": s.get("fee_etb_max"), "fee_has_usd": s.get("fee_has_usd", False),
            "online_url": s.get("online_url"), "source_url": s.get("source_url"),
            "source": "mesob", "last_verified": today,
        }
        for s in catalog["services"]
    ]
    center_fields = ("id", "name", "city", "latitude", "longitude", "map_url")
    links = [
        (doc_id, s["id"])
        for doc_id in catalog_service.DOCUMENT_SERVICE_RULES
        for s in catalog_service.services_for_document(doc_id)
    ]

    with connection() as conn, conn.transaction():
        for row in institutions:
            graph_store.merge_node("Institution", row["id"], row, conn)
        for row in services:
            graph_store.merge_node("GovService", row["id"], row, conn)
            graph_store.merge_edge("OFFERED_BY", ("GovService", row["id"]), ("Institution", row["institution_id"]),
                                   conn=conn)
        # Services removed from MESOB since the last sync
        removed = graph_store.delete_nodes_except("GovService", [s["id"] for s in services], {"source": "mesob"},
                                                  conn)
        for c in catalog["centers"]:
            graph_store.merge_node("MesobCenter", c["id"], {k: c.get(k) for k in center_fields}, conn)
        graph_store.delete_edges("FULFILLED_BY", src_label="Document", dst_label="GovService", conn=conn)
        linked = sum(
            graph_store.merge_edge("FULFILLED_BY", ("Document", doc), ("GovService", svc), conn=conn)
            for doc, svc in links
        )

    return {
        "institutions": len(institutions),
        "services": len(services),
        "services_removed": removed,
        "centers": len(catalog["centers"]),
        "document_links": linked,
    }


def graph_counts() -> dict:
    nodes = graph_store.count_by_label()
    rels = graph_store.count_by_type()
    stale = fetch_one(
        "select count(*)::int as c from graph_nodes where label = 'Document' and props @> '{\"stale\": true}'"
    )
    return {
        "nodes": nodes,
        "relationships": rels,
        "totalNodes": sum(nodes.values()),
        "totalRelationships": sum(rels.values()),
        "staleDocuments": stale["c"] if stale else 0,
    }


def flag_stale_documents(cutoff: date) -> dict:
    """Mark documents not checked since the cutoff as stale, and the rest as not stale."""
    row = fetch_one(
        """
        with flagged as (
          update graph_nodes
          set props = props || jsonb_build_object(
                'stale', props->>'last_verified' is null or (props->>'last_verified')::date < %(cutoff)s::date),
              updated_at = now()
          where label = 'Document'
          returning (props->>'stale')::boolean as stale
        )
        select count(*) filter (where stale)::int as stale, count(*)::int as total from flagged
        """,
        {"cutoff": cutoff.isoformat()},
    )
    row = row or {"stale": 0, "total": 0}
    return {"stale": row["stale"], "checked": row["total"], "cutoff": cutoff.isoformat()}


def _serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


# Each document with its direct prerequisites, the MESOB services that issue it and the goals it completes
_DOCUMENT_ROWS = """
        select d.props as doc,
          coalesce((select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.props->'name') order by p.id)
                    from graph_edges e join graph_nodes p on p.label = e.src_label and p.id = e.src_id
                    where e.type = 'REQUIRES' and e.src_label = 'Document'
                      and e.dst_label = 'Document' and e.dst_id = d.id), '[]') as prerequisites,
          coalesce((select jsonb_agg(jsonb_build_object('id', g.id, 'name', g.props->'name') order by g.id)
                    from graph_edges e join graph_nodes g on g.label = e.dst_label and g.id = e.dst_id
                    where e.type = 'FULFILLED_BY' and e.src_label = 'Document' and e.src_id = d.id
                      and e.dst_label = 'GovService'), '[]') as mesob_services,
          coalesce((select array_agg(e.src_id order by e.src_id) from graph_edges e
                    where e.type = 'TARGETS' and e.src_label = 'Service'
                      and e.dst_label = 'Document' and e.dst_id = d.id), '{}') as target_of
        from graph_nodes d
"""


def list_documents() -> list[dict]:
    rows = fetch_all(f"{_DOCUMENT_ROWS} where d.label = 'Document' order by d.props->>'name', d.id")
    out = []
    for r in rows:
        doc = {k: _serialize(v) for k, v in r["doc"].items()}
        doc["prerequisites"] = [p["id"] for p in r["prerequisites"]]
        doc["mesob_services"] = r["mesob_services"]
        doc["target_of"] = r["target_of"]
        out.append(doc)
    return out


def get_document(doc_id: str) -> dict | None:
    doc = graph_store.get_node("Document", doc_id)
    if doc is None:
        return None
    return {k: _serialize(v) for k, v in doc.items()}


def page_documents(
    q: str | None = None, status: str | None = None, limit: int = 20, offset: int = 0
) -> dict:
    """One page of Document nodes for the admin table, with search and a verified/stale filter."""
    where = [
        "d.label = 'Document'",
        "(%(q)s = '' or strpos(lower(coalesce(d.props->>'name', '')), %(q)s) > 0"
        " or strpos(lower(d.id), %(q)s) > 0"
        " or strpos(lower(coalesce(d.props->>'issuing_authority', '')), %(q)s) > 0)",
    ]
    if status == "stale":
        where.append("coalesce((d.props->>'stale')::boolean, false)")
    elif status == "verified":
        where.append("not coalesce((d.props->>'stale')::boolean, false)")
    params = {"q": (q or "").strip().lower(), "limit": limit, "offset": offset}
    cond = " and ".join(where)
    total = fetch_one(f"select count(*)::int as c from graph_nodes d where {cond}", params)
    rows = fetch_all(
        f"{_DOCUMENT_ROWS} where {cond} order by lower(d.props->>'name'), d.id offset %(offset)s limit %(limit)s",
        params,
    )
    items = []
    for r in rows:
        doc = {k: _serialize(v) for k, v in r["doc"].items()}
        pres = r["prerequisites"]
        doc["prerequisites"] = [p["id"] for p in pres]
        doc["prerequisite_names"] = {p["id"]: p.get("name") or p["id"] for p in pres}
        doc["mesob_services"] = r["mesob_services"]
        doc["target_of"] = r["target_of"]
        items.append(doc)
    return {"items": items, "total": total["c"] if total else 0}


def update_document(doc_id: str, changes: dict, *, mark_verified: bool, actor: str | None = None) -> dict | None:
    props = {k: v for k, v in changes.items() if k in EDITABLE_DOCUMENT_FIELDS}
    props["updated_by"] = actor
    props["updated_at"] = datetime.now(timezone.utc).isoformat()
    if mark_verified:
        props.update(last_verified=date.today().isoformat(), stale=False, verified_by=actor)
    with connection() as conn, conn.transaction():
        if not conn.execute("select 1 from graph_nodes where label = 'Document' and id = %s for update",
                            (doc_id,)).fetchone():
            return None
        doc = graph_store.merge_node("Document", doc_id, props, conn)
    return {k: _serialize(v) for k, v in doc.items()}


def compliance_graph_view() -> dict:
    """Every node a roadmap can touch and the links between them, for the admin diagram.

    Nodes carry a `key` ("Label:id") because services, documents and sectors share ids
    (e.g. "passport"). Edges are normalised so `source` always has to happen before
    `target`, whatever the direction of the stored relationship:
      REQUIRES      document -> document that needs it
      TARGETS       final document -> the goal (service) it completes
      SECTOR_EXTRA  extra document -> the business sector that needs it
      ORG_REQUIRES  document -> organization service that asks for it
      ISSUES        organization service -> document it hands out
      PREREQUISITE  organization service -> organization service that needs it first
    """
    rows = fetch_all(
        """
        select n.label as type, n.id, n.props, o.id as organization_id, o.props->>'name' as organization
        from graph_nodes n
        left join lateral (
          select org.id, org.props from graph_edges e
          join graph_nodes org on org.label = e.dst_label and org.id = e.dst_id
          where n.label = 'OrgService' and e.type = 'OFFERED_BY' and e.src_label = 'OrgService'
            and e.src_id = n.id and e.dst_label = 'Organization'
          order by org.id limit 1
        ) o on true
        where n.label in ('Service', 'Document', 'Sector', 'OrgDocument')
           or (n.label = 'OrgService' and coalesce((n.props->>'published')::boolean, false))
        """
    )

    def first(p: dict, *keys: str) -> Any:
        return next((p[k] for k in keys if p.get(k) is not None), None)

    nodes = []
    for r in rows:
        p = r["props"]
        nodes.append({
            "key": f"{r['type']}:{r['id']}", "id": r["id"], "type": r["type"],
            "label": first(p, "name", "label") or r["id"],
            "label_am": p.get("name_am"), "description": p.get("description"), "category": p.get("category"),
            "stale": p.get("stale"), "fee": first(p, "fee_etb", "fee_min"),
            "days": p.get("avg_processing_days"), "minutes": p.get("processing_minutes"),
            "office": first(p, "issuing_authority", "regulatory_body"), "form_code": p.get("form_code"),
            "last_verified": p.get("last_verified"), "verified_by": p.get("verified_by"),
            "source_url": p.get("source_url"), "sectors": p.get("applicable_sectors"),
            "sector_specific": p.get("sector_specific"), "slug": p.get("slug"),
            "organization": r["organization"], "organization_id": r["organization_id"],
        })
    edges = fetch_all(
        """
        select 'Document:' || src_id as source, 'Document:' || dst_id as target, 'REQUIRES' as type
        from graph_edges where type = 'REQUIRES' and src_label = 'Document' and dst_label = 'Document'
        union all
        select 'Document:' || dst_id, 'Service:' || src_id, 'TARGETS'
        from graph_edges where type = 'TARGETS' and src_label = 'Service' and dst_label = 'Document'
        union all
        select 'Document:' || dst_id, 'Sector:' || src_id, 'SECTOR_EXTRA'
        from graph_edges where type = 'SECTOR_EXTRA' and src_label = 'Sector' and dst_label = 'Document'
        union all
        select e.dst_label || ':' || e.dst_id, 'OrgService:' || e.src_id, 'ORG_REQUIRES'
        from graph_edges e join graph_nodes s on s.label = e.src_label and s.id = e.src_id
        where e.type = 'REQUIRES' and e.src_label = 'OrgService' and e.dst_label in ('Document', 'OrgDocument')
          and coalesce((s.props->>'published')::boolean, false)
        union all
        select 'OrgService:' || e.src_id, e.dst_label || ':' || e.dst_id, 'ISSUES'
        from graph_edges e join graph_nodes s on s.label = e.src_label and s.id = e.src_id
        where e.type = 'ISSUES' and e.src_label = 'OrgService' and e.dst_label in ('Document', 'OrgDocument')
          and coalesce((s.props->>'published')::boolean, false)
        union all
        select 'OrgService:' || e.dst_id, 'OrgService:' || e.src_id, 'PREREQUISITE'
        from graph_edges e
        join graph_nodes s on s.label = e.src_label and s.id = e.src_id
        join graph_nodes p on p.label = e.dst_label and p.id = e.dst_id
        where e.type = 'PREREQUISITE' and e.src_label = 'OrgService' and e.dst_label = 'OrgService'
          and coalesce((s.props->>'published')::boolean, false) and coalesce((p.props->>'published')::boolean, false)
        """
    )
    mesob = fetch_all(
        """
        select f.src_id as document, g.id, g.props->>'name' as name, i.props->>'short_name' as institution,
               g.props->>'fee_text' as fee_text, g.props->>'processing_time_text' as time_text
        from graph_edges f
        join graph_nodes g on g.label = f.dst_label and g.id = f.dst_id
        join graph_edges o on o.type = 'OFFERED_BY' and o.src_label = g.label and o.src_id = g.id
          and o.dst_label = 'Institution'
        join graph_nodes i on i.label = o.dst_label and i.id = o.dst_id
        where f.type = 'FULFILLED_BY' and f.src_label = 'Document' and f.dst_label = 'GovService'
        """
    )
    keys = {n["key"] for n in nodes}
    out_nodes = [{k: _serialize(v) for k, v in n.items()} for n in nodes]
    # Drop links to anything not drawn (unpublished services, half-synced nodes)
    out_edges = [e for e in edges if e["source"] in keys and e["target"] in keys and e["source"] != e["target"]]
    return {"nodes": out_nodes, "edges": out_edges, "mesobLinks": mesob}


def _institution_filter(q: str | None) -> tuple[str, dict]:
    cond = ("i.label = 'Institution' and i.props @> '{\"at_mesob\": true}'"
            " and (%(q)s = '' or strpos(lower(coalesce(i.props->>'name', '')), %(q)s) > 0"
            " or strpos(lower(coalesce(i.props->>'short_name', '')), %(q)s) > 0)")
    return cond, {"q": (q or "").strip().lower()}


def _institution_rows(cond: str) -> str:
    return f"""
        select i.id, i.props->>'name' as name, i.props->>'short_name' as short_name,
               count(g.id)::int as services,
               avg((g.props->>'processing_minutes')::float8) as avg_minutes,
               (count(g.id) filter (where g.props->>'online_url' is not null))::int as online
        from graph_nodes i
        left join graph_edges e on e.type = 'OFFERED_BY' and e.src_label = 'GovService'
          and e.dst_label = i.label and e.dst_id = i.id
        left join graph_nodes g on g.label = e.src_label and g.id = e.src_id and g.props->>'language' = 'en'
        where {cond}
        group by i.id, i.props
        order by services desc, name
    """


def institution_breakdown() -> list[dict]:
    cond, params = _institution_filter(None)
    return fetch_all(_institution_rows(cond), params)


def page_institutions(q: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    """One page of MESOB institutions with their service counts, busiest first."""
    cond, params = _institution_filter(q)
    rows = fetch_all(f"{_institution_rows(cond)} offset %(offset)s limit %(limit)s",
                     {**params, "limit": limit, "offset": offset})
    total = fetch_one(f"select count(*)::int as c from graph_nodes i where {cond}", params)
    return {"items": rows, "total": total["c"] if total else 0}
