import type { GraphEdgeType, GraphNode, GraphView } from "@cn/core/types/admin";

export const NODE_W = 168;
export const NODE_H = 54;
export const COL_GAP = 64;
export const ROW_GAP = 16;
export const HEADER_H = 28;
const MARGIN = 24;

export type PlacedNode = GraphNode & { x: number; y: number; layer: number; mesobCount: number };
export type PlacedEdge = { key: string; type: GraphEdgeType; from: PlacedNode; to: PlacedNode };
export type GraphLayout = {
  nodes: PlacedNode[];
  edges: PlacedEdge[];
  /** Column titles: "Step 1", "Step 2" … and "Not linked" for nodes with no links */
  columns: { x: number; title: string }[];
  width: number;
  height: number;
};

/** Ancestors (what must happen first) and descendants (what depends on it) of one node. */
export function relatives(view: Pick<GraphView, "edges">, key: string) {
  const preds = new Map<string, string[]>();
  const succs = new Map<string, string[]>();
  for (const e of view.edges) {
    (preds.get(e.target) ?? preds.set(e.target, []).get(e.target)!).push(e.source);
    (succs.get(e.source) ?? succs.set(e.source, []).get(e.source)!).push(e.target);
  }
  const walk = (start: string, next: Map<string, string[]>) => {
    const seen = new Set<string>();
    const stack = [...(next.get(start) ?? [])];
    while (stack.length) {
      const k = stack.pop()!;
      if (seen.has(k) || k === start) continue;
      seen.add(k);
      stack.push(...(next.get(k) ?? []));
    }
    return seen;
  };
  return {
    directPrereqs: preds.get(key) ?? [],
    directDependants: succs.get(key) ?? [],
    prereqs: walk(key, preds),
    dependants: walk(key, succs),
  };
}

const TYPE_ORDER: Record<GraphNode["type"], number> = {
  Document: 0,
  OrgDocument: 1,
  OrgService: 2,
  Service: 3,
  Sector: 4,
};

/**
 * Layered (Sugiyama-style) layout, left to right by dependency depth:
 * 1. drop edges that would close a cycle (the data should be a DAG; this keeps a bad edge from hanging the page),
 * 2. each node's column is the longest chain of prerequisites before it,
 * 3. nodes inside a column are ordered by the average position of their neighbours, swept a few
 *    times in both directions, which removes most edge crossings cheaply,
 * 4. nodes with no links at all go in a last "Not linked" column so gaps in the data stand out.
 */
export function layoutGraph(view: GraphView): GraphLayout {
  const byKey = new Map(view.nodes.map((n) => [n.key, n]));
  const edges = view.edges.filter((e) => byKey.has(e.source) && byKey.has(e.target) && e.source !== e.target);

  const succs = new Map<string, string[]>(view.nodes.map((n) => [n.key, []]));
  for (const e of edges) succs.get(e.source)!.push(e.target);

  // 1. Cycle breaking by DFS: an edge into a node still on the stack is a back edge
  const state = new Map<string, 1 | 2>();
  const back = new Set<string>();
  const sortedKeys = [...byKey.keys()].sort();
  for (const root of sortedKeys) {
    if (state.has(root)) continue;
    const stack: [string, number][] = [[root, 0]];
    state.set(root, 1);
    while (stack.length) {
      const top = stack[stack.length - 1];
      const out = succs.get(top[0])!;
      if (top[1] < out.length) {
        const next = out[top[1]++];
        const s = state.get(next);
        if (s === 1) back.add(`${top[0]}>${next}`);
        else if (!s) {
          state.set(next, 1);
          stack.push([next, 0]);
        }
      } else {
        state.set(top[0], 2);
        stack.pop();
      }
    }
  }
  const dag = edges.filter((e) => !back.has(`${e.source}>${e.target}`));

  // 2. Longest-path layering (iterative topological order, no recursion depth limits)
  const indeg = new Map<string, number>(view.nodes.map((n) => [n.key, 0]));
  const out = new Map<string, string[]>(view.nodes.map((n) => [n.key, []]));
  const inc = new Map<string, string[]>(view.nodes.map((n) => [n.key, []]));
  for (const e of dag) {
    indeg.set(e.target, indeg.get(e.target)! + 1);
    out.get(e.source)!.push(e.target);
    inc.get(e.target)!.push(e.source);
  }
  const layer = new Map<string, number>();
  const queue = sortedKeys.filter((k) => indeg.get(k) === 0);
  queue.forEach((k) => layer.set(k, 0));
  for (let i = 0; i < queue.length; i++) {
    const k = queue[i];
    for (const t of out.get(k)!) {
      layer.set(t, Math.max(layer.get(t) ?? 0, layer.get(k)! + 1));
      indeg.set(t, indeg.get(t)! - 1);
      if (indeg.get(t) === 0) queue.push(t);
    }
  }

  const linked = new Set<string>();
  for (const e of edges) {
    linked.add(e.source);
    linked.add(e.target);
  }
  const depth = Math.max(0, ...[...linked].map((k) => layer.get(k) ?? 0));
  const isolatedCol = depth + 1;
  const columns: string[][] = Array.from({ length: depth + 2 }, () => []);
  for (const n of view.nodes) {
    const c = linked.has(n.key) ? (layer.get(n.key) ?? 0) : isolatedCol;
    columns[c].push(n.key);
  }
  const label = (k: string) => byKey.get(k)!;
  for (const col of columns) {
    col.sort((a, b) => TYPE_ORDER[label(a).type] - TYPE_ORDER[label(b).type] || label(a).label.localeCompare(label(b).label));
  }

  // 3. Barycenter sweeps to reduce crossings
  const pos = new Map<string, number>();
  const index = () => columns.forEach((col) => col.forEach((k, i) => pos.set(k, i)));
  index();
  const reorder = (col: string[], neighbours: Map<string, string[]>) => {
    const score = new Map<string, number>();
    col.forEach((k, i) => {
      const ns = neighbours.get(k)!;
      score.set(k, ns.length ? ns.reduce((sum, n) => sum + pos.get(n)!, 0) / ns.length : i);
    });
    col.sort((a, b) => score.get(a)! - score.get(b)!);
    col.forEach((k, i) => pos.set(k, i));
  };
  for (let sweep = 0; sweep < 4; sweep++) {
    for (let c = 1; c <= depth; c++) reorder(columns[c], inc);
    for (let c = depth - 1; c >= 0; c--) reorder(columns[c], out);
  }

  // 4. Coordinates: columns centred on the tallest one
  const tallest = Math.max(1, ...columns.map((c) => c.length));
  const bandH = tallest * NODE_H + (tallest - 1) * ROW_GAP;
  const top = MARGIN + HEADER_H;
  const colX = (i: number) => MARGIN + i * (NODE_W + COL_GAP);

  const mesobCounts = new Map<string, number>();
  for (const l of view.mesobLinks) mesobCounts.set(l.document, (mesobCounts.get(l.document) ?? 0) + 1);

  const placed = new Map<string, PlacedNode>();
  const titles: GraphLayout["columns"] = [];
  columns.forEach((col, ci) => {
    if (!col.length) return;
    const h = col.length * NODE_H + (col.length - 1) * ROW_GAP;
    const y0 = top + Math.max(0, (bandH - h) / 2);
    titles.push({ x: colX(ci), title: ci === isolatedCol ? "Not linked" : `Step ${ci + 1}` });
    col.forEach((k, ri) => {
      const n = byKey.get(k)!;
      placed.set(k, {
        ...n,
        x: colX(ci),
        y: y0 + ri * (NODE_H + ROW_GAP),
        layer: ci,
        mesobCount: n.type === "Document" ? (mesobCounts.get(n.id) ?? 0) : 0,
      });
    });
  });

  const placedEdges: PlacedEdge[] = edges.map((e) => ({
    key: `${e.type}:${e.source}>${e.target}`,
    type: e.type,
    from: placed.get(e.source)!,
    to: placed.get(e.target)!,
  }));

  const nodes = [...placed.values()];
  const width = nodes.length ? Math.max(...nodes.map((n) => n.x + NODE_W)) + MARGIN : 0;
  const height = top + bandH + MARGIN;
  return { nodes, edges: placedEdges, columns: titles, width, height };
}

/** A smooth curve from the right side of `from` to the left side of `to`; back edges loop underneath. */
export function edgePath({ from, to }: PlacedEdge): string {
  const y1 = from.y + NODE_H / 2;
  const y2 = to.y + NODE_H / 2;
  if (to.x > from.x) {
    const x1 = from.x + NODE_W;
    const x2 = to.x - 6;
    const bend = Math.max(24, (x2 - x1) / 2);
    return `M${x1},${y1} C${x1 + bend},${y1} ${x2 - bend},${y2} ${x2},${y2}`;
  }
  const x1 = from.x + NODE_W / 2;
  const x2 = to.x + NODE_W / 2;
  const low = Math.max(from.y, to.y) + NODE_H + 40;
  return `M${x1},${from.y + NODE_H} C${x1},${low} ${x2},${low} ${x2},${to.y + NODE_H + 6}`;
}
