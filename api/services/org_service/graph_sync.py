"""Keeping the knowledge graph in step with published organization services."""

from __future__ import annotations

import logging

from services.db import fetch_one

log = logging.getLogger(__name__)


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
