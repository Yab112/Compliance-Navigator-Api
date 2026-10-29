import type { GraphNode, GraphView } from "@/types/admin";

/** Services, documents and sectors share ids (e.g. "passport"), so nodes are keyed by type. */
export const nodeKey = (type: GraphNode["type"], id: string) => `${type}:${id}`;

export const NODE_W = 140;
export const NODE_H = 46;
const COL_GAP = 46;
const ROW_GAP = 18;
const BAND_GAP = 56;
const MARGIN = 16;

export type PlacedNode = GraphNode & { key: string; x: number; y: number; mesobCount: number };
export type PlacedEdge = {
  key: string;
  type: GraphView["edges"][number]["type"];
  from: PlacedNode;
  to: PlacedNode;
};

/**
 * Layered layout: documents in columns by longest REQUIRES depth (prerequisites on the
 * left), services in a band above the document they target, sectors in a band below.
 */
export function layoutGraph(view: GraphView) {
  const docs = view.nodes.filter((n) => n.type === "Document");
  const requires = view.edges.filter((e) => e.type === "REQUIRES");
  const preds = new Map<string, string[]>(docs.map((d) => [d.id, []]));
  for (const e of requires) preds.get(e.target)?.push(e.source);

  const depth = new Map<string, number>();
  const visiting = new Set<string>();
  const depthOf = (id: string): number => {
    if (depth.has(id)) return depth.get(id)!;
    if (visiting.has(id)) return 0; // cycle guard, the graph should be a DAG
    visiting.add(id);
    const d = Math.max(-1, ...(preds.get(id) ?? []).map(depthOf)) + 1;
    visiting.delete(id);
    depth.set(id, d);
    return d;
  };
  docs.forEach((d) => depthOf(d.id));

  const columns: GraphNode[][] = [];
  for (const d of docs) (columns[depth.get(d.id) ?? 0] ??= []).push(d);
  columns.forEach((c) => c?.sort((a, b) => a.label.localeCompare(b.label)));

  const tallest = Math.max(1, ...columns.map((c) => c?.length ?? 0));
  const docBandTop = MARGIN + NODE_H + BAND_GAP;
  const docBandH = tallest * NODE_H + (tallest - 1) * ROW_GAP;
  const sectorTop = docBandTop + docBandH + BAND_GAP;
  const colX = (i: number) => MARGIN + i * (NODE_W + COL_GAP);

  const mesobCounts = new Map<string, number>();
  for (const l of view.mesobLinks) mesobCounts.set(l.document, (mesobCounts.get(l.document) ?? 0) + 1);

  const placed = new Map<string, PlacedNode>();
  columns.forEach((col, ci) => {
    if (!col) return;
    const colH = col.length * NODE_H + (col.length - 1) * ROW_GAP;
    const top = docBandTop + (docBandH - colH) / 2;
    col.forEach((d, ri) => {
      const key = nodeKey("Document", d.id);
      placed.set(key, { ...d, key, x: colX(ci), y: top + ri * (NODE_H + ROW_GAP), mesobCount: mesobCounts.get(d.id) ?? 0 });
    });
  });

  // Services / sectors sit over / under their document; collisions shift right by a slot
  const placeBand = (type: "Service" | "Sector", edgeType: "TARGETS" | "SECTOR_EXTRA", y: number) => {
    const taken = new Set<number>();
    const nodes = view.nodes.filter((n) => n.type === type);
    const anchored = nodes.map((n) => {
      const edge = view.edges.find((e) => e.type === edgeType && e.source === n.id);
      const doc = edge ? placed.get(nodeKey("Document", edge.target)) : undefined;
      return { n, slot: doc ? Math.round((doc.x - MARGIN) / (NODE_W + COL_GAP)) : null };
    });
    anchored.sort((a, b) => (a.slot ?? 1e9) - (b.slot ?? 1e9));
    for (const { n, slot } of anchored) {
      let s = slot ?? 0;
      while (taken.has(s)) s += 1;
      taken.add(s);
      const key = nodeKey(type, n.id);
      placed.set(key, { ...n, key, x: colX(s), y, mesobCount: 0 });
    }
  };
  placeBand("Service", "TARGETS", MARGIN);
  placeBand("Sector", "SECTOR_EXTRA", sectorTop);

  const edges: PlacedEdge[] = [];
  for (const e of view.edges) {
    const fromType = e.type === "REQUIRES" ? "Document" : e.type === "TARGETS" ? "Service" : "Sector";
    const from = placed.get(nodeKey(fromType, e.source));
    const to = placed.get(nodeKey("Document", e.target));
    if (from && to) edges.push({ key: `${e.type}:${e.source}->${e.target}`, type: e.type, from, to });
  }

  const nodes = [...placed.values()];
  const width = Math.max(...nodes.map((n) => n.x + NODE_W)) + MARGIN;
  const height = sectorTop + NODE_H + MARGIN;
  return { nodes, edges, width, height };
}

/** Edge geometry: REQUIRES runs left→right, TARGETS drops down, SECTOR_EXTRA rises up. */
export function edgePath(e: PlacedEdge): string {
  const { from, to } = e;
  if (e.type === "REQUIRES") {
    const x1 = from.x + NODE_W;
    const y1 = from.y + NODE_H / 2;
    const x2 = to.x - 4;
    const y2 = to.y + NODE_H / 2;
    const mid = (x1 + x2) / 2;
    return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`;
  }
  const x1 = from.x + NODE_W / 2;
  const x2 = to.x + NODE_W / 2;
  if (e.type === "TARGETS") {
    const y1 = from.y + NODE_H;
    const y2 = to.y - 4;
    return `M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}`;
  }
  const y1 = from.y;
  const y2 = to.y + NODE_H + 4;
  return `M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}`;
}
