"""
Validate compliance graph integrity.

Run from api/:  uv run python -m scripts.validate_graph
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import graph_store  # noqa: E402
from services.db import fetch_all  # noqa: E402


def _without_link(label: str, type: str, target_label: str, extra: str = "") -> list[str]:
    """Ids of `label` nodes with no outgoing `type` link to a `target_label` node."""
    rows = fetch_all(
        f"""
        select n.id from graph_nodes n
        where n.label = %(label)s {extra}
          and not exists (select 1 from graph_edges e
                          where e.type = %(type)s and e.src_label = n.label and e.src_id = n.id
                            and e.dst_label = %(target)s)
        order by n.id
        """,
        {"label": label, "type": type, "target": target_label},
    )
    return [r["id"] for r in rows]


def main() -> None:
    errors: list[str] = []

    for sid in _without_link("Service", "TARGETS", "Document"):
        errors.append(f"Service '{sid}' has no TARGETS document")

    sub_city_offices = "and n.id like '%%\\_%%' and n.id not like '%%\\_main'"
    for oid in _without_link("Office", "LOCATED_IN", "SubCity", sub_city_offices)[:20]:
        errors.append(f"Sub-city office '{oid}' missing LOCATED_IN")

    for did in _without_link("Document", "ISSUED_BY", "Office"):
        errors.append(f"Document '{did}' has no ISSUED_BY office")

    nodes, rels = graph_store.count_by_label(), graph_store.count_by_type()
    print(
        f"Graph: {nodes.get('Service', 0)} services, {nodes.get('Document', 0)} documents, "
        f"{nodes.get('SubCity', 0)} sub-cities, {rels.get('REQUIRES', 0)} REQUIRES edges"
    )

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("Validation passed.")


if __name__ == "__main__":
    main()
