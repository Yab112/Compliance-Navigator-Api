"""Neo4j maintenance for the admin dashboard: MESOB sync, stats, stale checks, editing."""

from __future__ import annotations

import re
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


def get_document(doc_id: str) -> dict | None:
    rows = _query_rows("MATCH (d:Document {id: $id}) RETURN properties(d) AS doc", {"id": doc_id})
    if not rows:
        return None
    return {k: _serialize(v) for k, v in dict(rows[0]["doc"]).items()}


def page_documents(
    q: str | None = None, status: str | None = None, limit: int = 20, offset: int = 0
) -> dict:
    """One page of Document nodes for the admin table, with search and a verified/stale filter."""
    search = (
        "($q = '' OR toLower(d.name) CONTAINS $q OR toLower(d.id) CONTAINS $q"
        " OR toLower(coalesce(d.issuing_authority, '')) CONTAINS $q)"
    )
    where = [search]
    if status == "stale":
        where.append("coalesce(d.stale, false) = true")
    elif status == "verified":
        where.append("coalesce(d.stale, false) = false")
    params = {"q": (q or "").strip().lower(), "limit": limit, "offset": offset}
    cond = " AND ".join(where)
    total = _query_rows(f"MATCH (d:Document) WHERE {cond} RETURN count(d) AS c", params)
    rows = _query_rows(
        f"""
        MATCH (d:Document) WHERE {cond}
        WITH d ORDER BY toLower(d.name), d.id SKIP $offset LIMIT $limit
        OPTIONAL MATCH (pre:Document)-[:REQUIRES]->(d)
        OPTIONAL MATCH (d)-[:FULFILLED_BY]->(g:GovService)
        OPTIONAL MATCH (s:Service)-[:TARGETS]->(d)
        RETURN properties(d) AS doc,
               collect(DISTINCT {{id: pre.id, name: pre.name}}) AS prerequisites,
               collect(DISTINCT {{id: g.id, name: g.name}}) AS mesob_services,
               collect(DISTINCT s.id) AS target_of
        ORDER BY toLower(doc.name), doc.id
        """,
        params,
    )
    items = []
    for r in rows:
        doc = {k: _serialize(v) for k, v in dict(r["doc"]).items()}
        pres = [p for p in r["prerequisites"] if p.get("id")]
        doc["prerequisites"] = [p["id"] for p in pres]
        doc["prerequisite_names"] = {p["id"]: p.get("name") or p["id"] for p in pres}
        doc["mesob_services"] = [m for m in r["mesob_services"] if m.get("id")]
        doc["target_of"] = r["target_of"]
        items.append(doc)
    return {"items": items, "total": total[0]["c"] if total else 0}


def update_document(doc_id: str, changes: dict, *, mark_verified: bool, actor: str | None = None) -> dict | None:
    props = {k: v for k, v in changes.items() if k in EDITABLE_DOCUMENT_FIELDS}
    props["updated_by"] = actor
    rows = _query_rows(
        """
        MATCH (d:Document {id: $id})
        SET d += $props, d.updated_at = datetime()
        FOREACH (_ IN CASE WHEN $verify THEN [1] ELSE [] END |
          SET d.last_verified = date(), d.stale = false, d.verified_by = $actor)
        RETURN properties(d) AS doc
        """,
        {"id": doc_id, "props": props, "verify": mark_verified, "actor": actor},
    )
    if not rows:
        return None
    return {k: _serialize(v) for k, v in dict(rows[0]["doc"]).items()}


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
    nodes = _query_rows(
        """
        MATCH (n) WHERE n:Service OR n:Document OR n:Sector OR n:OrgDocument
                     OR (n:OrgService AND coalesce(n.published, false))
        WITH n, labels(n)[0] AS type
        OPTIONAL MATCH (n)-[:OFFERED_BY]->(o:Organization) WHERE type = 'OrgService'
        RETURN type + ':' + coalesce(n.id, n.key) AS key, coalesce(n.id, n.key) AS id, type,
               coalesce(n.name, n.label, n.id, n.key) AS label,
               n.name_am AS label_am, n.description AS description, n.category AS category,
               n.stale AS stale, coalesce(n.fee_etb, n.fee_min) AS fee,
               n.avg_processing_days AS days, n.processing_minutes AS minutes,
               coalesce(n.issuing_authority, n.regulatory_body) AS office, n.form_code AS form_code,
               n.last_verified AS last_verified, n.verified_by AS verified_by,
               n.source_url AS source_url, n.applicable_sectors AS sectors,
               n.sector_specific AS sector_specific, n.slug AS slug,
               o.name AS organization, o.id AS organization_id
        """
    )
    edges = _query_rows(
        """
        MATCH (a:Document)-[:REQUIRES]->(b:Document)
        RETURN 'Document:' + a.id AS source, 'Document:' + b.id AS target, 'REQUIRES' AS type
        UNION ALL
        MATCH (s:Service)-[:TARGETS]->(d:Document)
        RETURN 'Document:' + d.id AS source, 'Service:' + s.id AS target, 'TARGETS' AS type
        UNION ALL
        MATCH (sec:Sector)-[:SECTOR_EXTRA]->(d:Document)
        RETURN 'Document:' + d.id AS source, 'Sector:' + sec.id AS target, 'SECTOR_EXTRA' AS type
        UNION ALL
        MATCH (s:OrgService)-[:REQUIRES]->(d) WHERE coalesce(s.published, false) AND (d:Document OR d:OrgDocument)
        RETURN labels(d)[0] + ':' + coalesce(d.id, d.key) AS source, 'OrgService:' + s.id AS target,
               'ORG_REQUIRES' AS type
        UNION ALL
        MATCH (s:OrgService)-[:ISSUES]->(d) WHERE coalesce(s.published, false) AND (d:Document OR d:OrgDocument)
        RETURN 'OrgService:' + s.id AS source, labels(d)[0] + ':' + coalesce(d.id, d.key) AS target,
               'ISSUES' AS type
        UNION ALL
        MATCH (s:OrgService)-[:PREREQUISITE]->(p:OrgService)
        WHERE coalesce(s.published, false) AND coalesce(p.published, false)
        RETURN 'OrgService:' + p.id AS source, 'OrgService:' + s.id AS target, 'PREREQUISITE' AS type
        """
    )
    mesob = _query_rows(
        """
        MATCH (d:Document)-[:FULFILLED_BY]->(g:GovService)-[:OFFERED_BY]->(i:Institution)
        RETURN d.id AS document, g.id AS id, g.name AS name, i.short_name AS institution,
               g.fee_text AS fee_text, g.processing_time_text AS time_text
        """
    )
    keys = {n["key"] for n in nodes if n["key"]}
    out_nodes = []
    for n in nodes:
        if not n["key"]:
            continue
        out_nodes.append({k: _serialize(v) for k, v in n.items()})
    # Drop links to anything not drawn (unpublished services, half-synced nodes)
    out_edges = [e for e in edges if e["source"] in keys and e["target"] in keys and e["source"] != e["target"]]
    return {"nodes": out_nodes, "edges": out_edges, "mesobLinks": mesob}


def _institution_filter(q: str | None) -> tuple[str, dict]:
    cond = ("i.at_mesob = true AND ($q = '' OR toLower(coalesce(i.name, '')) CONTAINS $q"
            " OR toLower(coalesce(i.short_name, '')) CONTAINS $q)")
    return cond, {"q": (q or "").strip().lower()}


_INSTITUTION_ROWS = """
        OPTIONAL MATCH (g:GovService {language: 'en'})-[:OFFERED_BY]->(i)
        RETURN i.id AS id, i.name AS name, i.short_name AS short_name,
               count(g) AS services,
               avg(g.processing_minutes) AS avg_minutes,
               count(CASE WHEN g.online_url IS NOT NULL THEN 1 END) AS online
        ORDER BY services DESC, name
"""


def institution_breakdown() -> list[dict]:
    cond, params = _institution_filter(None)
    return _query_rows(f"MATCH (i:Institution) WHERE {cond} {_INSTITUTION_ROWS}", params)


def page_institutions(q: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    """One page of MESOB institutions with their service counts, busiest first."""
    cond, params = _institution_filter(q)
    rows = _query_rows(
        f"MATCH (i:Institution) WHERE {cond} {_INSTITUTION_ROWS} SKIP $offset LIMIT $limit",
        {**params, "limit": limit, "offset": offset},
    )
    total = _query_rows(f"MATCH (i:Institution) WHERE {cond} RETURN count(i) AS c", params)
    return {"items": rows, "total": total[0]["c"] if total else 0}


# ---------------------------------------------------------------- read-only Cypher console

CYPHER_TIMEOUT_SECONDS = 10
CYPHER_MAX_ROWS = 200


class CypherRejected(ValueError):
    """The console query does something other than read the graph."""


# Clauses that change data or schema, read files or URLs, or run admin commands. Neo4j also
# refuses writes because the session is READ-only; this list is the first line of defence and
# covers reads we do not want either (LOAD CSV can fetch URLs, dbms.* and SHOW leak config).
_FORBIDDEN = [
    (r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|FOREACH|ALTER|RENAME|GRANT|DENY|REVOKE)\b",
     "writes are not allowed"),
    (r"\bLOAD\s+CSV\b", "LOAD CSV is not allowed"),
    (r"\bUSING\s+PERIODIC\s+COMMIT\b|\bIN\s+(CONCURRENT\s+)?TRANSACTIONS\b", "batched transactions are not allowed"),
    (r"\b(SHOW|START|STOP|TERMINATE|ENABLE|USE)\b", "admin commands are not allowed"),
    (r"\b(apoc|dbms|gds)\s*\.", "APOC, GDS and dbms functions are not allowed"),
]
# CALL is limited to these read-only listings
_ALLOWED_CALLS = {"db.labels", "db.relationshiptypes", "db.propertykeys", "db.schema.visualization",
                  "db.schema.nodetypeproperties", "db.schema.reltypeproperties"}


def _strip_literals(query: str) -> str:
    """Blank out comments and string literals so 'Set' inside a name is not a keyword."""
    out = re.sub(r"//[^\n]*|/\*.*?\*/", " ", query, flags=re.DOTALL)
    out = re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`", "''", out)
    return out


def check_readonly_cypher(query: str) -> None:
    code = _strip_literals(query)
    for pattern, reason in _FORBIDDEN:
        if re.search(pattern, code, flags=re.IGNORECASE):
            raise CypherRejected(f"Rejected: {reason}. This console only reads the graph.")
    for call in re.finditer(r"\bCALL\b\s*([\w.]*)", code, flags=re.IGNORECASE):
        name = call.group(1).lower()
        if name not in _ALLOWED_CALLS:
            what = f"the procedure {name}" if name else "a CALL { ... } subquery"
            allowed = ", ".join(sorted(_ALLOWED_CALLS))
            raise CypherRejected(f"Rejected: {what} is not allowed here. Allowed procedures: {allowed}.")


def run_cypher_readonly(query: str, params: dict | None = None, limit: int = CYPHER_MAX_ROWS) -> dict:
    """Read-only Cypher console for admins.

    Three guards: the keyword check above, a READ session (Neo4j refuses any write), and a
    server-side transaction timeout. At most `limit` rows are fetched; `truncated` says if more existed.
    """
    import neo4j
    from neontology import GraphConnection

    check_readonly_cypher(query)
    driver = GraphConnection().engine.driver

    @neo4j.unit_of_work(timeout=CYPHER_TIMEOUT_SECONDS)
    def work(tx):
        result = tx.run(query, params or {})
        rows = result.fetch(limit + 1)
        result.consume()
        return rows

    with driver.session(default_access_mode=neo4j.READ_ACCESS) as session:
        records = session.execute_read(work)
    rows = [{k: _jsonable(v) for k, v in rec.items()} for rec in records[:limit]]
    return {"rows": rows, "truncated": len(records) > limit, "limit": limit}


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
