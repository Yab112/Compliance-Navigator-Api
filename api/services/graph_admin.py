"""Neo4j maintenance for the admin dashboard: MESOB sync, stats, stale checks, editing."""

from __future__ import annotations

from datetime import date
from typing import Any

from services import catalog_service
from services.graph_service import _query_rows

BATCH = 200

# Properties an admin may edit on a Document node from the dashboard
EDITABLE_DOCUMENT_FIELDS = {
    "name", "name_am", "issuing_authority", "form_code", "fee_etb",
    "avg_processing_days", "legal_basis", "source_url",
    "required_input_labels", "rejection_reasons",
}


def _chunks(rows: list[dict], size: int = BATCH):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def sync_catalog_to_graph() -> dict:
    """Mirror the MESOB snapshot into Neo4j and link roadmap documents to it."""
    catalog = catalog_service.load_catalog()
    today = date.today().isoformat()

    _query_rows("CREATE CONSTRAINT gov_service_id IF NOT EXISTS FOR (n:GovService) REQUIRE n.id IS UNIQUE")
    _query_rows("CREATE CONSTRAINT institution_id IF NOT EXISTS FOR (n:Institution) REQUIRE n.id IS UNIQUE")
    _query_rows("CREATE CONSTRAINT mesob_center_id IF NOT EXISTS FOR (n:MesobCenter) REQUIRE n.id IS UNIQUE")

    institutions = [
        {
            "id": i["id"], "name": i.get("name"), "name_am": i.get("name_am"),
            "short_name": i.get("short_name"), "logo_url": i.get("logo_url"),
            "service_count": i.get("service_count", 0),
        }
        for i in catalog["institutions"]
    ]
    _query_rows(
        """
        UNWIND $rows AS row
        MERGE (i:Institution {id: row.id})
        SET i.name = row.name, i.name_am = row.name_am, i.short_name = row.short_name,
            i.logo_url = row.logo_url, i.service_count = row.service_count,
            i.at_mesob = true, i.scrape_method = 'mesob_api'
        """,
        {"rows": institutions},
    )

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
        }
        for s in catalog["services"]
    ]
    for batch in _chunks(services):
        _query_rows(
            """
            UNWIND $rows AS row
            MERGE (g:GovService {id: row.id})
            SET g += row, g.source = 'mesob', g.last_verified = date($today)
            WITH g, row
            MATCH (i:Institution {id: row.institution_id})
            MERGE (g)-[:OFFERED_BY]->(i)
            """,
            {"rows": batch, "today": today},
        )

    # Services removed from MESOB since the last sync
    removed = _query_rows(
        """
        MATCH (g:GovService {source: 'mesob'}) WHERE NOT g.id IN $ids
        DETACH DELETE g RETURN count(*) AS c
        """,
        {"ids": [s["id"] for s in services]},
    )

    _query_rows(
        """
        UNWIND $rows AS row
        MERGE (c:MesobCenter {id: row.id})
        SET c.name = row.name, c.city = row.city, c.latitude = row.latitude,
            c.longitude = row.longitude, c.map_url = row.map_url
        """,
        {"rows": catalog["centers"]},
    )

    links = [
        {"doc": doc_id, "svc": s["id"]}
        for doc_id in catalog_service.DOCUMENT_SERVICE_RULES
        for s in catalog_service.services_for_document(doc_id)
    ]
    _query_rows("MATCH (:Document)-[r:FULFILLED_BY]->(:GovService) DELETE r")
    linked = _query_rows(
        """
        UNWIND $rows AS row
        MATCH (d:Document {id: row.doc}), (g:GovService {id: row.svc})
        MERGE (d)-[:FULFILLED_BY]->(g)
        RETURN count(*) AS c
        """,
        {"rows": links},
    )

    return {
        "institutions": len(institutions),
        "services": len(services),
        "services_removed": removed[0]["c"] if removed else 0,
        "centers": len(catalog["centers"]),
        "document_links": linked[0]["c"] if linked else 0,
    }


def graph_counts() -> dict:
    labels = _query_rows(
        "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY count DESC"
    )
    rels = _query_rows(
        "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC"
    )
    stale = _query_rows("MATCH (d:Document) WHERE d.stale = true RETURN count(d) AS c")
    return {
        "nodes": {r["label"]: r["count"] for r in labels},
        "relationships": {r["type"]: r["count"] for r in rels},
        "totalNodes": sum(r["count"] for r in labels),
        "totalRelationships": sum(r["count"] for r in rels),
        "staleDocuments": stale[0]["c"] if stale else 0,
    }


def flag_stale_documents(cutoff: date) -> dict:
    rows = _query_rows(
        """
        MATCH (d:Document)
        WITH d, (d.last_verified IS NULL OR d.last_verified < date($cutoff)) AS is_stale
        SET d.stale = is_stale
        RETURN count(CASE WHEN is_stale THEN 1 END) AS stale, count(d) AS total
        """,
        {"cutoff": cutoff.isoformat()},
    )
    row = rows[0] if rows else {"stale": 0, "total": 0}
    return {"stale": row["stale"], "checked": row["total"], "cutoff": cutoff.isoformat()}


def _serialize(value: Any) -> Any:
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


def list_documents() -> list[dict]:
    rows = _query_rows(
        """
        MATCH (d:Document)
        OPTIONAL MATCH (pre:Document)-[:REQUIRES]->(d)
        OPTIONAL MATCH (d)-[:FULFILLED_BY]->(g:GovService)
        OPTIONAL MATCH (s:Service)-[:TARGETS]->(d)
        RETURN d AS doc,
               collect(DISTINCT pre.id) AS prerequisites,
               collect(DISTINCT {id: g.id, name: g.name}) AS mesob_services,
               collect(DISTINCT s.id) AS target_of
        ORDER BY d.name
        """
    )
    out = []
    for r in rows:
        doc = {k: _serialize(v) for k, v in dict(r["doc"]).items()}
        doc["prerequisites"] = r["prerequisites"]
        doc["mesob_services"] = [m for m in r["mesob_services"] if m.get("id")]
        doc["target_of"] = r["target_of"]
        out.append(doc)
    return out


def update_document(doc_id: str, changes: dict, *, mark_verified: bool) -> dict | None:
    props = {k: v for k, v in changes.items() if k in EDITABLE_DOCUMENT_FIELDS}
    rows = _query_rows(
        """
        MATCH (d:Document {id: $id})
        SET d += $props
        FOREACH (_ IN CASE WHEN $verify THEN [1] ELSE [] END |
          SET d.last_verified = date(), d.stale = false)
        RETURN d AS doc
        """,
        {"id": doc_id, "props": props, "verify": mark_verified},
    )
    if not rows:
        return None
    return {k: _serialize(v) for k, v in dict(rows[0]["doc"]).items()}


def compliance_graph_view() -> dict:
    """Services, documents and their edges, small enough to draw in full."""
    nodes = _query_rows(
        """
        MATCH (n) WHERE n:Service OR n:Document OR n:Sector
        RETURN n.id AS id, coalesce(n.name, n.label) AS label, labels(n)[0] AS type,
               n.stale AS stale, n.fee_etb AS fee, n.avg_processing_days AS days
        """
    )
    edges = _query_rows(
        """
        MATCH (a)-[r:REQUIRES|TARGETS|SECTOR_EXTRA]->(b)
        RETURN a.id AS source, b.id AS target, type(r) AS type
        """
    )
    mesob = _query_rows(
        """
        MATCH (d:Document)-[:FULFILLED_BY]->(g:GovService)-[:OFFERED_BY]->(i:Institution)
        RETURN d.id AS document, g.id AS id, g.name AS name, i.short_name AS institution
        """
    )
    return {"nodes": nodes, "edges": edges, "mesobLinks": mesob}


def institution_breakdown() -> list[dict]:
    return _query_rows(
        """
        MATCH (i:Institution {at_mesob: true})
        OPTIONAL MATCH (g:GovService {language: 'en'})-[:OFFERED_BY]->(i)
        RETURN i.id AS id, i.name AS name, i.short_name AS short_name,
               count(g) AS services,
               avg(g.processing_minutes) AS avg_minutes,
               count(CASE WHEN g.online_url IS NOT NULL THEN 1 END) AS online
        ORDER BY services DESC
        """
    )


def run_cypher_readonly(query: str, params: dict | None = None, limit: int = 200) -> list[dict]:
    """Read-only Cypher console for admins. Writes are rejected by the driver."""
    from neontology import GraphConnection

    gc = GraphConnection()
    driver = gc.engine.driver
    with driver.session(default_access_mode="READ") as session:
        result = session.execute_read(lambda tx: list(tx.run(query, params or {}))[:limit])
    return [{k: _jsonable(v) for k, v in rec.items()} for rec in result]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "items") and hasattr(value, "labels"):
        return {"_labels": list(value.labels), **{k: _jsonable(v) for k, v in value.items()}}
    if hasattr(value, "type") and hasattr(value, "start_node"):
        return {"_type": value.type, **{k: _jsonable(v) for k, v in value.items()}}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return _serialize(value)
