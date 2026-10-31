"""
Copy the compliance graph from Neo4j into Postgres (graph_nodes and graph_edges), once, when moving off Neo4j.

Run from api/:  uv sync --group migrate
                uv run python -m scripts.copy_graph_from_neo4j --dry-run   (counts only, writes nothing)
                uv run python -m scripts.copy_graph_from_neo4j

Reads NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD from the environment (or .env) and writes to DATABASE_URL.
Every node and link is copied as it is: its first label, its id (the `id` property, or `key`, or `email`),
and its properties as JSON with dates as ISO strings. Running it again overwrites the same rows, so it is
safe to repeat. Nodes and links that exist only in Postgres are left alone.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import dotenv_values  # noqa: E402

from services.db import Jsonb, connection, run_migrations  # noqa: E402

ID_PROPERTIES = ("id", "key", "email")


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or dotenv_values(".env").get(name) or default


def _plain(value: Any) -> Any:
    """Neo4j values as JSON: temporal values become ISO strings, anything else unknown becomes text."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if hasattr(value, "iso_format"):
        return value.iso_format()
    return str(value)


def read_neo4j() -> tuple[list[dict], list[dict]]:
    import neo4j

    uri, user, password = _env("NEO4J_URI", "bolt://localhost:7687"), _env("NEO4J_USERNAME", "neo4j"), _env("NEO4J_PASSWORD")
    if not password:
        sys.exit("Set NEO4J_PASSWORD (and NEO4J_URI, NEO4J_USERNAME) to the Neo4j to copy from.")
    with neo4j.GraphDatabase.driver(uri, auth=(user, password)) as driver, driver.session() as session:
        nodes = [dict(r) for r in session.run(
            "MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props")]
        rels = [dict(r) for r in session.run(
            "MATCH (a)-[r]->(b) RETURN type(r) AS type, elementId(a) AS src, elementId(b) AS dst, properties(r) AS props")]
    return nodes, rels


def convert(nodes: list[dict], rels: list[dict]) -> tuple[list[tuple], list[tuple], list[str]]:
    """Rows for graph_nodes and graph_edges, and warnings about anything that does not fit."""
    warnings: list[str] = []
    by_eid: dict[str, tuple[str, str]] = {}
    node_rows: dict[tuple[str, str], dict] = {}
    for n in nodes:
        if not n["labels"]:
            warnings.append(f"node {n['eid']} has no label, skipped")
            continue
        if len(n["labels"]) > 1:
            warnings.append(f"node {n['eid']} has labels {n['labels']}, kept {n['labels'][0]}")
        props = _plain(n["props"])
        node_id = next((str(props[k]) for k in ID_PROPERTIES if props.get(k) is not None), n["eid"])
        key = (n["labels"][0], node_id)
        if key in node_rows:
            warnings.append(f"two nodes are {key[0]}:{key[1]}, their properties were combined")
            props = {**node_rows[key], **props}
        node_rows[key] = props
        by_eid[n["eid"]] = key
    edge_rows: dict[tuple, dict] = {}
    for r in rels:
        src, dst = by_eid.get(r["src"]), by_eid.get(r["dst"])
        if not src or not dst:
            warnings.append(f"{r['type']} link from a skipped node, skipped")
            continue
        key = (r["type"], *src, *dst)
        if key in edge_rows:
            warnings.append(f"two {r['type']} links from {src} to {dst}, their properties were combined")
        edge_rows[key] = {**edge_rows.get(key, {}), **_plain(r["props"])}
    return (
        [(label, node_id, Jsonb(props)) for (label, node_id), props in node_rows.items()],
        [(*key, Jsonb(props)) for key, props in edge_rows.items()],
        warnings,
    )


def _counts(rows: list[tuple], index: int) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[row[index]] = out.get(row[index], 0) + 1
    return dict(sorted(out.items()))


def write(node_rows: list[tuple], edge_rows: list[tuple]) -> None:
    with connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            """
            insert into graph_nodes (label, id, props) values (%s, %s, %s)
            on conflict (label, id) do update set props = excluded.props, updated_at = now()
            """,
            node_rows,
        )
        cur.executemany(
            """
            insert into graph_edges (type, src_label, src_id, dst_label, dst_id, props) values (%s, %s, %s, %s, %s, %s)
            on conflict (type, src_label, src_id, dst_label, dst_id) do update set props = excluded.props
            """,
            edge_rows,
        )


def postgres_counts() -> tuple[dict[str, int], dict[str, int]]:
    with connection() as conn:
        labels = conn.execute("select label, count(*)::int as c from graph_nodes group by label").fetchall()
        types = conn.execute("select type, count(*)::int as c from graph_edges group by type").fetchall()
    return dict(sorted((r["label"], r["c"]) for r in labels)), dict(sorted((r["type"], r["c"]) for r in types))


def _print_counts(title: str, nodes: dict[str, int], edges: dict[str, int]) -> None:
    print(f"{title}: {sum(nodes.values())} nodes, {sum(edges.values())} links")
    for k, v in nodes.items():
        print(f"  node {k:16s} {v}")
    for k, v in edges.items():
        print(f"  link {k:16s} {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="read Neo4j and print counts, write nothing")
    args = parser.parse_args()

    nodes, rels = read_neo4j()
    node_rows, edge_rows, warnings = convert(nodes, rels)
    print(f"Neo4j: {len(nodes)} nodes, {len(rels)} relationships")
    for w in warnings:
        print(f"  warning: {w}")
    _print_counts("To copy", _counts(node_rows, 0), _counts(edge_rows, 0))
    if args.dry_run:
        print("Dry run: nothing written.")
        return

    run_migrations()
    write(node_rows, edge_rows)
    _print_counts("Postgres now has", *postgres_counts())


if __name__ == "__main__":
    main()
