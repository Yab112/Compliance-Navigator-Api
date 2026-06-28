"""
Validate compliance graph integrity.

Run from api/:  uv run python -m scripts.validate_graph
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.database import initiate_database
from services.graph_service import _query_rows


def main() -> None:
    initiate_database()
    errors: list[str] = []

    for row in _query_rows(
        """
        MATCH (s:Service)
        WHERE NOT (s)-[:TARGETS]->(:Document)
        RETURN s.id AS id
        """
    ):
        errors.append(f"Service '{row['id']}' has no TARGETS document")

    for row in _query_rows(
        """
        MATCH (o:Office)
        WHERE o.id CONTAINS '_'
          AND NOT o.id ENDS WITH '_main'
          AND NOT (o)-[:LOCATED_IN]->(:SubCity)
        RETURN o.id AS id
        LIMIT 20
        """
    ):
        errors.append(f"Sub-city office '{row['id']}' missing LOCATED_IN")

    for row in _query_rows(
        """
        MATCH (d:Document)
        WHERE NOT (d)-[:ISSUED_BY]->(:Office)
        RETURN d.id AS id
        """
    ):
        errors.append(f"Document '{row['id']}' has no ISSUED_BY office")

    counts = _query_rows(
        """
        OPTIONAL MATCH (s:Service) WITH count(s) AS services
        OPTIONAL MATCH (d:Document) WITH services, count(d) AS documents
        OPTIONAL MATCH (sc:SubCity) WITH services, documents, count(sc) AS subcities
        OPTIONAL MATCH ()-[r:REQUIRES]->() WITH services, documents, subcities, count(r) AS requires
        RETURN services, documents, subcities, requires
        """
    )
    if counts:
        c = counts[0]
        print(
            f"Graph: {c['services']} services, {c['documents']} documents, "
            f"{c['subcities']} sub-cities, {c['requires']} REQUIRES edges"
        )

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("Validation passed.")


if __name__ == "__main__":
    main()
