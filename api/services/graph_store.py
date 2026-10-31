"""The compliance graph in Postgres: nodes in graph_nodes, links in graph_edges (db/migrations/036).

A node is (label, id) plus a JSON object of properties. An edge is (type, source node, target node)
plus its own properties; deleting a node deletes its edges. Every helper takes an optional psycopg
connection so a caller can change graph rows in the same transaction as its other Postgres rows.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterable, Iterator
from uuid import UUID

from services.db import Jsonb, connection

Node = tuple[str, str]  # (label, id)

# How far ancestors_via follows links; real prerequisite chains are a handful of steps long
MAX_DEPTH = 50


@contextmanager
def _conn(conn: Any = None) -> Iterator[Any]:
    if conn is not None:
        yield conn
    else:
        with connection() as c:
            yield c


def _all(sql: str, params: dict | tuple | None = None, conn: Any = None) -> list[dict]:
    with _conn(conn) as c:
        return list(c.execute(sql, params).fetchall())


def _one(sql: str, params: dict | tuple | None = None, conn: Any = None) -> dict | None:
    with _conn(conn) as c:
        return c.execute(sql, params).fetchone()


def _count(sql: str, params: dict | tuple | None = None, conn: Any = None) -> int:
    with _conn(conn) as c:
        return c.execute(sql, params).rowcount


def jsonable(value: Any) -> Any:
    """Dates as ISO strings, ids as text, the way the graph stores them."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    return value


# ---------------------------------------------------------------- nodes


def merge_node(label: str, id: str, props: dict | None = None, conn: Any = None) -> dict:
    """Create the node or add these properties to it (a None value removes that property).

    The same as Cypher `MERGE (n:Label {id: $id}) SET n += $props`. Returns the stored properties.
    """
    new = Jsonb(jsonable(props or {}))
    row = _one(
        """
        insert into graph_nodes (label, id, props) values (%(label)s, %(id)s, jsonb_strip_nulls(%(props)s))
        on conflict (label, id) do update
          set props = jsonb_strip_nulls(graph_nodes.props || %(props)s), updated_at = now()
        returning props
        """,
        {"label": label, "id": id, "props": new},
        conn,
    )
    return row["props"]


def merge_nodes(label: str, rows: Iterable[tuple[str, dict]], conn: Any = None) -> int:
    """merge_node for many nodes of one label, in one transaction."""
    count = 0
    with _conn(conn) as c, c.transaction():
        for node_id, props in rows:
            merge_node(label, node_id, props, c)
            count += 1
    return count


def get_node(label: str, id: str, conn: Any = None) -> dict | None:
    row = _one("select props from graph_nodes where label = %s and id = %s", (label, id), conn)
    return row["props"] if row else None


def find_nodes(
    label: str,
    *,
    filters: dict | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    conn: Any = None,
) -> list[dict]:
    """Properties of the nodes with this label, by name. `filters` must all match exactly; `search`
    is a case-insensitive text match on the name or id."""
    where = ["label = %(label)s"]
    params: dict[str, Any] = {"label": label, "offset": offset, "limit": limit}
    if filters:
        where.append("props @> %(filters)s")
        params["filters"] = Jsonb(jsonable(filters))
    if search and search.strip():
        where.append("(strpos(lower(coalesce(props->>'name', '')), %(q)s) > 0 or strpos(lower(id), %(q)s) > 0)")
        params["q"] = search.strip().lower()
    rows = _all(
        f"select props from graph_nodes where {' and '.join(where)} "
        "order by lower(props->>'name'), id offset %(offset)s limit %(limit)s",
        params,
        conn,
    )
    return [r["props"] for r in rows]


def neighbors(label: str, id: str, type: str | None = None, direction: str = "out", conn: Any = None) -> list[dict]:
    """Nodes linked to this one. direction "out" follows links that start here, "in" links that end here.

    Each item is {"label", "id", "props", "edge"} where edge holds the link's own properties.
    """
    if direction == "out":
        here, there = ("src_label", "src_id"), ("dst_label", "dst_id")
    elif direction == "in":
        here, there = ("dst_label", "dst_id"), ("src_label", "src_id")
    else:
        raise ValueError("direction must be 'out' or 'in'")
    type_cond = "and e.type = %(type)s" if type else ""
    return _all(
        f"""
        select n.label, n.id, n.props, e.props as edge, e.type
        from graph_edges e join graph_nodes n on n.label = e.{there[0]} and n.id = e.{there[1]}
        where e.{here[0]} = %(label)s and e.{here[1]} = %(id)s {type_cond}
        order by n.label, n.id
        """,
        {"label": label, "id": id, "type": type},
        conn,
    )


def delete_node(label: str, id: str, conn: Any = None) -> int:
    """Delete the node and every link to or from it."""
    return _count("delete from graph_nodes where label = %s and id = %s", (label, id), conn)


def delete_nodes_except(label: str, keep_ids: list[str], filters: dict | None = None, conn: Any = None) -> int:
    """Delete nodes of this label (matching `filters`) whose id is not in keep_ids."""
    cond = "and props @> %(filters)s" if filters else ""
    return _count(
        f"delete from graph_nodes where label = %(label)s and not (id = any(%(keep)s)) {cond}",
        {"label": label, "keep": list(keep_ids), "filters": Jsonb(jsonable(filters or {}))},
        conn,
    )


# ---------------------------------------------------------------- edges


def merge_edge(type: str, src: Node, dst: Node, props: dict | None = None, conn: Any = None) -> bool:
    """Link two existing nodes (adding `props` to the link). False when either node does not exist."""
    return bool(_count(
        """
        insert into graph_edges (type, src_label, src_id, dst_label, dst_id, props)
        select %(type)s, a.label, a.id, b.label, b.id, jsonb_strip_nulls(%(props)s)
        from graph_nodes a, graph_nodes b
        where a.label = %(sl)s and a.id = %(si)s and b.label = %(dl)s and b.id = %(di)s
        on conflict (type, src_label, src_id, dst_label, dst_id) do update
          set props = jsonb_strip_nulls(graph_edges.props || %(props)s)
        """,
        {"type": type, "sl": src[0], "si": src[1], "dl": dst[0], "di": dst[1],
         "props": Jsonb(jsonable(props or {}))},
        conn,
    ))


def delete_edges(
    type: str | list[str] | None = None,
    *,
    src: Node | None = None,
    dst: Node | None = None,
    src_label: str | None = None,
    dst_label: str | None = None,
    conn: Any = None,
) -> int:
    """Delete the links that match every given condition (at least one is required)."""
    where: list[str] = []
    params: dict[str, Any] = {}
    if type is not None:
        where.append("type = any(%(types)s)")
        params["types"] = [type] if isinstance(type, str) else list(type)
    if src:
        where.append("src_label = %(sl)s and src_id = %(si)s")
        params.update(sl=src[0], si=src[1])
    if dst:
        where.append("dst_label = %(dl)s and dst_id = %(di)s")
        params.update(dl=dst[0], di=dst[1])
    if src_label:
        where.append("src_label = %(src_label)s")
        params["src_label"] = src_label
    if dst_label:
        where.append("dst_label = %(dst_label)s")
        params["dst_label"] = dst_label
    if not where:
        raise ValueError("delete_edges needs at least one condition")
    return _count(f"delete from graph_edges where {' and '.join(where)}", params, conn)


def ancestors_via(type: str, label: str, id: str, max_depth: int = MAX_DEPTH, conn: Any = None) -> list[Node]:
    """Every node with a path of `type` links to this node, like Cypher `(a)-[:TYPE*]->(node)`.

    Safe on cycles: each node is visited once per depth and the walk stops at max_depth.
    """
    rows = _all(
        """
        with recursive up (label, id, depth) as (
          select src_label, src_id, 1 from graph_edges
          where type = %(type)s and dst_label = %(label)s and dst_id = %(id)s
          union
          select e.src_label, e.src_id, up.depth + 1
          from graph_edges e join up on e.dst_label = up.label and e.dst_id = up.id
          where e.type = %(type)s and up.depth < %(max)s
        )
        select distinct label, id from up order by label, id
        """,
        {"type": type, "label": label, "id": id, "max": max_depth},
        conn,
    )
    return [(r["label"], r["id"]) for r in rows]


# ---------------------------------------------------------------- counts


def count_by_label(conn: Any = None) -> dict[str, int]:
    rows = _all("select label, count(*)::int as c from graph_nodes group by label order by c desc, label", conn=conn)
    return {r["label"]: r["c"] for r in rows}


def count_by_type(conn: Any = None) -> dict[str, int]:
    rows = _all("select type, count(*)::int as c from graph_edges group by type order by c desc, type", conn=conn)
    return {r["type"]: r["c"] for r in rows}
