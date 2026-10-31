"""Keeping the knowledge graph in step with published organization services."""

from __future__ import annotations

from typing import Any

from services import graph_store
from services.db import connection

# ---------------------------------------------------------------- knowledge graph


def sync_service_to_graph(service_id: str, conn: Any = None) -> bool:
    """Mirror a published service into the graph.

    Pass the connection of the transaction that publishes the service, so the service and its graph
    nodes are saved (or rolled back) together. Returns False when the service has nothing published.
    """
    if conn is None:
        with connection() as c, c.transaction():
            return sync_service_to_graph(service_id, c)
    row = conn.execute(
        """
        select s.published_snapshot as snap, o.id::text as org_id, o.name as org_name, o.slug as org_slug,
               o.org_type, o.catalog_institution_id
        from org_services s join organizations o on o.id = s.org_id
        where s.id = %s and s.published_snapshot is not null
        """,
        (service_id,),
    ).fetchone()
    if not row:
        return False
    snap = row["snap"]
    org = ("Organization", row["org_id"])
    svc = ("OrgService", service_id)

    graph_store.merge_node(*org, {"id": row["org_id"], "name": row["org_name"], "slug": row["org_slug"],
                                  "org_type": row["org_type"]}, conn)
    if row["catalog_institution_id"]:
        graph_store.merge_edge("SAME_AS", org, ("Institution", row["catalog_institution_id"]), conn=conn)
    graph_store.merge_node(*svc, {"id": service_id, "name": snap["name"], "slug": snap["slug"],
                                  "fee_min": snap.get("fee_amount_min"),
                                  "processing_minutes": snap.get("processing_minutes"), "published": True}, conn)
    graph_store.merge_edge("OFFERED_BY", svc, org, conn=conn)
    graph_store.delete_edges(["REQUIRES", "ISSUES", "PREREQUISITE"], src=svc, conn=conn)

    # Linked documents reuse the compliance graph's Document nodes; free-text ones get an OrgDocument
    def document(entry: dict) -> tuple[str, str]:
        if entry.get("document_id"):
            return "Document", entry["document_id"]
        key = entry["name"].strip().lower()
        if graph_store.get_node("OrgDocument", key, conn) is None:
            graph_store.merge_node("OrgDocument", key, {"key": key, "name": entry["name"]}, conn)
        return "OrgDocument", key

    for r in snap.get("requirements") or []:
        graph_store.merge_edge("REQUIRES", svc, document(r),
                               {"conditional": r["required"] == "conditional", "key": r["key"]}, conn)
    for pid in sorted({r["issuing_service_id"] for r in snap.get("requirements") or [] if r.get("issuing_service_id")}):
        graph_store.merge_node("OrgService", pid, {"id": pid}, conn)
        graph_store.merge_edge("PREREQUISITE", svc, ("OrgService", pid), conn=conn)
    for o in snap.get("outputs") or []:
        graph_store.merge_edge("ISSUES", svc, document(o), conn=conn)
    return True


def remove_service_from_graph(service_id: str, conn: Any = None) -> None:
    """Delete the service's graph node and its links."""
    graph_store.delete_node("OrgService", service_id, conn)
