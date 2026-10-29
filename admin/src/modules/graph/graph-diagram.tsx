"use client";

import { memo, useCallback, useEffect, useId, useImperativeHandle, useRef, useState } from "react";
import { ChartTheme } from "@cn/ui/charts/chart-theme";
import { cn } from "@cn/core/lib/utils";
import { NODE_H, NODE_W, edgePath, type GraphLayout, type PlacedNode } from "@/modules/graph/graph-layout";
import { EDGE_TYPES, HIGHLIGHT, NODE_TYPES, formatDuration, formatFee } from "@/modules/graph/graph-style";

type Transform = { x: number; y: number; k: number };
const MIN_K = 0.1;
const MAX_K = 2.5;
const PAD = 40;
/** Below this zoom labels get hard to read, so the first view starts here and scrolls instead. */
const READABLE_K = 0.6;

const MARKER_COLORS: string[] = [
  ...new Set([...Object.values(EDGE_TYPES).map((s) => s.color), HIGHLIGHT.prereq, HIGHLIGHT.dependant]),
];

export type Highlight = { prereqs: Set<string>; dependants: Set<string> } | null;
export type GraphDiagramHandle = { centerOn: (key: string) => void; fit: () => void };

function truncate(text: string, max: number) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function nodeMeta(n: PlacedNode): string {
  switch (n.type) {
    case "Document":
      return `${formatFee(n.fee)} · ${formatDuration(n.days)}`;
    case "OrgService":
      return n.organization ?? formatDuration(null, n.minutes);
    case "Sector":
      return n.office ?? "Business sector";
    case "Service":
      return n.category ? `Goal · ${n.category}` : "Goal";
    default:
      return "Not matched to a document";
  }
}

type SceneProps = {
  layout: GraphLayout;
  selectedKey: string | null;
  highlight: Highlight;
  matches: Set<string>;
  markerId: (color: string) => string;
  onNodeClick: (key: string) => void;
};

/** Everything inside the pan/zoom group. Memoised so dragging only re-renders the transform. */
const Scene = memo(function Scene({ layout, selectedKey, highlight, matches, markerId, onNodeClick }: SceneProps) {
  const inPath = (key: string) =>
    key === selectedKey || !!highlight?.prereqs.has(key) || !!highlight?.dependants.has(key);
  const edgeColor = (from: string, to: string, base: string) => {
    if (!highlight) return { color: base, dim: false };
    const isFrom = (k: string) => k === selectedKey;
    if ((highlight.prereqs.has(from) || isFrom(from)) && (highlight.prereqs.has(to) || isFrom(to)) && !isFrom(from))
      return { color: HIGHLIGHT.prereq, dim: false };
    if ((highlight.dependants.has(from) || isFrom(from)) && (highlight.dependants.has(to) || isFrom(to)) && !isFrom(to))
      return { color: HIGHLIGHT.dependant, dim: false };
    return { color: base, dim: true };
  };

  return (
    <>
      {layout.columns.map((c) => (
        <text key={c.title} x={c.x} y={34} style={{ fill: "var(--muted-foreground)" }} className="text-[11px] font-semibold">
          {c.title}
        </text>
      ))}
      {layout.edges.map((e) => {
        const style = EDGE_TYPES[e.type];
        const { color, dim } = edgeColor(e.from.key, e.to.key, style.color);
        return (
          <path
            key={e.key}
            d={edgePath(e)}
            fill="none"
            style={{ stroke: color }}
            strokeWidth={dim || !highlight ? 1.5 : 2.5}
            strokeDasharray={style.dashed ? "5 4" : undefined}
            opacity={dim ? 0.12 : 0.9}
            markerEnd={`url(#${markerId(color)})`}
          />
        );
      })}
      {layout.nodes.map((n) => {
        const selected = n.key === selectedKey;
        const stale = n.type === "Document" && !!n.stale;
        const dim = !!highlight && !inPath(n.key);
        const ring = selected
          ? "var(--foreground)"
          : highlight?.prereqs.has(n.key)
            ? HIGHLIGHT.prereq
            : highlight?.dependants.has(n.key)
              ? HIGHLIGHT.dependant
              : matches.has(n.key)
                ? "var(--primary)"
                : stale
                  ? HIGHLIGHT.stale
                  : "var(--border)";
        const thick = selected || matches.has(n.key) || (!!highlight && !dim) || stale;
        return (
          <g
            key={n.key}
            transform={`translate(${n.x},${n.y})`}
            className="cursor-pointer"
            opacity={dim ? 0.3 : 1}
            data-node={n.key}
            onClick={(ev) => {
              ev.stopPropagation();
              onNodeClick(n.key);
            }}
          >
            <title>{`${NODE_TYPES[n.type].label}: ${n.label}${stale ? " (stale)" : ""}`}</title>
            <rect
              width={NODE_W}
              height={NODE_H}
              style={{ fill: "var(--card)", stroke: ring }}
              strokeWidth={thick ? 2 : 1}
              strokeDasharray={n.type === "OrgDocument" ? "4 3" : undefined}
            />
            <rect width={4} height={NODE_H} style={{ fill: NODE_TYPES[n.type].color }} />
            <text x={12} y={15} style={{ fill: "var(--muted-foreground)" }} className="text-[9px] tracking-wide uppercase">
              {NODE_TYPES[n.type].label}
              {stale ? " · ▲ stale" : ""}
            </text>
            <text x={12} y={31} style={{ fill: "var(--foreground)" }} className="text-[11px] font-semibold">
              {truncate(n.label, 25)}
            </text>
            <text x={12} y={46} style={{ fill: "var(--muted-foreground)" }} className="text-[9.5px]">
              {truncate(nodeMeta(n), n.mesobCount ? 18 : 28)}
            </text>
            {n.mesobCount > 0 && (
              <g transform={`translate(${NODE_W - 52},${NODE_H - 16})`}>
                <rect width={46} height={12} style={{ fill: "var(--primary)" }} opacity={0.15} />
                <text x={23} y={9} textAnchor="middle" style={{ fill: "var(--primary)" }} className="text-[8px] font-semibold">
                  MESOB ×{n.mesobCount}
                </text>
              </g>
            )}
          </g>
        );
      })}
    </>
  );
});

function ZoomButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className="border-border bg-background hover:bg-muted focus-visible:ring-ring/50 h-8 min-w-8 border px-1.5 text-xs font-medium outline-none focus-visible:ring-2"
    >
      {children}
    </button>
  );
}

type GraphDiagramProps = {
  layout: GraphLayout;
  selectedKey: string | null;
  highlight: Highlight;
  matches: Set<string>;
  onSelect: (key: string | null) => void;
  ref?: React.Ref<GraphDiagramHandle>;
};

/**
 * Pan and zoom viewport for the layered graph. Drag to move, Ctrl/⌘ + wheel (or pinch) to zoom,
 * plain wheel scrolls inside the box until it reaches an edge, then lets the page scroll.
 */
export function GraphDiagram({ layout, selectedKey, highlight, matches, onSelect, ref }: GraphDiagramProps) {
  const uid = useId().replace(/:/g, "");
  const helpId = `${uid}-help`;
  const boxRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  // The transform belongs to one layout; a new layout (filters changed) starts from its own first view
  const [view, setView] = useState<{ layout: GraphLayout | null; t: Transform }>({ layout: null, t: { x: 0, y: 0, k: 1 } });
  const drag = useRef<{ id: number; sx: number; sy: number; ox: number; oy: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setSize({ w: entry.contentRect.width, h: entry.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const clamp = useCallback(
    (n: Transform): Transform => {
      const k = Math.min(MAX_K, Math.max(MIN_K, n.k));
      const axis = (v: number, content: number, viewport: number) =>
        content + 2 * PAD <= viewport
          ? Math.min(Math.max(v, PAD / 2), viewport - content - PAD / 2)
          : Math.min(PAD, Math.max(v, viewport - content - PAD));
      return { k, x: axis(n.x, layout.width * k, size.w), y: axis(n.y, layout.height * k, size.h) };
    },
    [layout.width, layout.height, size.w, size.h],
  );

  const fitTransform = useCallback(
    (minK = MIN_K): Transform => {
      if (!size.w || !layout.width) return { x: 0, y: 0, k: 1 };
      const k = Math.max(minK, Math.min(1.2, (size.w - PAD) / layout.width, (size.h - PAD) / layout.height));
      // Too big to fit at a readable size: start at the top left, where the first steps are
      const x = layout.width * k > size.w ? PAD / 2 : (size.w - layout.width * k) / 2;
      const y = layout.height * k > size.h ? PAD / 2 : (size.h - layout.height * k) / 2;
      return clamp({ k, x, y });
    },
    [clamp, layout.width, layout.height, size.w, size.h],
  );

  const t = view.layout === layout ? view.t : fitTransform(READABLE_K);
  const tRef = useRef(t);
  useEffect(() => {
    tRef.current = t;
  });

  const update = useCallback(
    (fn: (cur: Transform) => Transform) => setView({ layout, t: clamp(fn(tRef.current)) }),
    [layout, clamp],
  );

  const zoomAt = useCallback(
    (factor: number, px = size.w / 2, py = size.h / 2) =>
      update((cur) => {
        const k = Math.min(MAX_K, Math.max(MIN_K, cur.k * factor));
        return { k, x: px - ((px - cur.x) * k) / cur.k, y: py - ((py - cur.y) * k) / cur.k };
      }),
    [update, size.w, size.h],
  );

  const fit = useCallback(() => setView({ layout, t: fitTransform() }), [layout, fitTransform]);

  useImperativeHandle(
    ref,
    () => ({
      fit,
      centerOn: (key: string) => {
        const n = layout.nodes.find((node) => node.key === key);
        if (!n) return;
        update((cur) => {
          const k = Math.max(cur.k, 0.8);
          return { k, x: size.w / 2 - (n.x + NODE_W / 2) * k, y: size.h / 2 - (n.y + NODE_H / 2) * k };
        });
        boxRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      },
    }),
    [fit, layout.nodes, update, size.w, size.h],
  );

  // Wheel needs a non-passive listener so it can stop the page from scrolling while the graph moves
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      const cur = tRef.current;
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const rect = el.getBoundingClientRect();
        zoomAt(Math.exp(-e.deltaY * 0.0025), e.clientX - rect.left, e.clientY - rect.top);
        return;
      }
      const dx = e.shiftKey && !e.deltaX ? e.deltaY : e.deltaX;
      const dy = e.shiftKey && !e.deltaX ? 0 : e.deltaY;
      const next = clamp({ ...cur, x: cur.x - dx, y: cur.y - dy });
      if (Math.abs(next.x - cur.x) < 0.5 && Math.abs(next.y - cur.y) < 0.5) return; // at the edge: let the page scroll
      e.preventDefault();
      setView({ layout, t: next });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [clamp, zoomAt, layout]);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    suppressClick.current = false;
    drag.current = { id: e.pointerId, sx: e.clientX, sy: e.clientY, ox: tRef.current.x, oy: tRef.current.y, moved: false };
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX - d.sx;
    const dy = e.clientY - d.sy;
    if (!d.moved && Math.hypot(dx, dy) < 4) return;
    if (!d.moved) {
      d.moved = true;
      e.currentTarget.setPointerCapture(e.pointerId);
    }
    update((cur) => ({ ...cur, x: d.ox + dx, y: d.oy + dy }));
  };
  const endDrag = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    if (d.moved) suppressClick.current = true;
    drag.current = null;
  };

  const onNodeClick = useCallback(
    (key: string) => {
      if (suppressClick.current) {
        suppressClick.current = false;
        return;
      }
      onSelect(key === selectedKey ? null : key);
    },
    [onSelect, selectedKey],
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const step = 80;
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [step, 0],
      ArrowRight: [-step, 0],
      ArrowUp: [0, step],
      ArrowDown: [0, -step],
    };
    if (moves[e.key]) {
      e.preventDefault();
      const [dx, dy] = moves[e.key];
      update((cur) => ({ ...cur, x: cur.x + dx, y: cur.y + dy }));
    } else if (e.key === "+" || e.key === "=") {
      e.preventDefault();
      zoomAt(1.25);
    } else if (e.key === "-" || e.key === "_") {
      e.preventDefault();
      zoomAt(0.8);
    } else if (e.key === "0") {
      e.preventDefault();
      fit();
    } else if (e.key === "Escape" && selectedKey) {
      onSelect(null);
    }
  };

  const markerId = useCallback((color: string) => `${uid}-arrow-${MARKER_COLORS.indexOf(color)}`, [uid]);

  return (
    <div className="viz-root relative">
      <ChartTheme />
      <p id={helpId} className="sr-only">
        Drag or use the arrow keys to move around. Hold Ctrl or Command and scroll, or press plus and minus, to zoom.
        Press 0 to fit everything. Use the search box above to pick an item, then follow its links in the details panel.
      </p>
      <div
        ref={boxRef}
        tabIndex={0}
        role="group"
        aria-roledescription="diagram"
        aria-label={`Compliance dependency graph, ${layout.nodes.length} items and ${layout.edges.length} links`}
        aria-describedby={helpId}
        className="border-border bg-muted/20 focus-visible:ring-ring/50 relative h-[60vh] max-h-[680px] min-h-80 cursor-grab touch-none overflow-hidden border outline-none select-none focus-visible:ring-2 active:cursor-grabbing"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        onClick={() => {
          if (suppressClick.current) {
            suppressClick.current = false;
            return;
          }
          if (selectedKey) onSelect(null);
        }}
      >
        <svg width="100%" height="100%" className="block" aria-hidden="true">
          <defs>
            {MARKER_COLORS.map((color, i) => (
              <marker
                key={color}
                id={`${uid}-arrow-${i}`}
                viewBox="0 0 8 8"
                refX="7"
                refY="4"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M0,0 L8,4 L0,8 z" style={{ fill: color }} />
              </marker>
            ))}
          </defs>
          <g transform={`translate(${t.x},${t.y}) scale(${t.k})`}>
            <Scene
              layout={layout}
              selectedKey={selectedKey}
              highlight={highlight}
              matches={matches}
              markerId={markerId}
              onNodeClick={onNodeClick}
            />
          </g>
        </svg>
      </div>
      <div className="absolute top-2 right-2 flex flex-col gap-1" role="toolbar" aria-label="Zoom">
        <ZoomButton label="Zoom in" onClick={() => zoomAt(1.25)}>
          +
        </ZoomButton>
        <ZoomButton label="Zoom out" onClick={() => zoomAt(0.8)}>
          −
        </ZoomButton>
        <ZoomButton label="Fit the whole graph on screen" onClick={() => fit()}>
          Fit
        </ZoomButton>
        <ZoomButton label="Actual size" onClick={() => zoomAt(1 / tRef.current.k)}>
          1:1
        </ZoomButton>
      </div>
      <p className="bg-background/80 text-muted-foreground pointer-events-none absolute bottom-2 left-2 px-1.5 py-0.5 text-[10px] tabular-nums">
        {Math.round(t.k * 100)}% · drag to move · Ctrl/⌘ + scroll to zoom
      </p>
    </div>
  );
}

export function GraphLegend({ layout, className }: { layout: GraphLayout; className?: string }) {
  const types = new Set(layout.nodes.map((n) => n.type));
  const edgeTypes = new Set(layout.edges.map((e) => e.type));
  const anyStale = layout.nodes.some((n) => n.type === "Document" && n.stale);
  const anyMesob = layout.nodes.some((n) => n.mesobCount > 0);
  return (
    <div className={cn("viz-root text-muted-foreground space-y-1.5 text-[11px]", className)}>
      <ChartTheme />
      <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-label="Kinds of item">
        {Object.entries(NODE_TYPES)
          .filter(([type]) => types.has(type as PlacedNode["type"]))
          .map(([type, s]) => (
            <li key={type} className="flex items-center gap-1.5">
              <span className={cn("border-border inline-block h-3 w-4 border border-l-4", type === "OrgDocument" && "border-dashed")} style={{ borderLeftColor: s.color }} />
              {s.label}
            </li>
          ))}
        {anyStale && (
          <li className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-4 border-2" style={{ borderColor: HIGHLIGHT.stale }} /> ▲ Stale: not checked in 30 days
          </li>
        )}
        {anyMesob && (
          <li className="flex items-center gap-1.5">
            <span className="bg-primary/15 text-primary px-1 text-[9px] font-medium">MESOB</span> Can be done at a MESOB center
          </li>
        )}
      </ul>
      <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-label="Kinds of link">
        {Object.entries(EDGE_TYPES)
          .filter(([type]) => edgeTypes.has(type as keyof typeof EDGE_TYPES))
          .map(([type, s]) => (
            <li key={type} className="flex items-center gap-1.5">
              <svg width="22" height="8" aria-hidden="true">
                <line x1="0" y1="4" x2="22" y2="4" style={{ stroke: s.color }} strokeWidth="2" strokeDasharray={s.dashed ? "4 3" : undefined} />
              </svg>
              {s.label}
            </li>
          ))}
        <li className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-5" style={{ background: HIGHLIGHT.prereq }} /> Prerequisites of the selected item
        </li>
        <li className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-5" style={{ background: HIGHLIGHT.dependant }} /> Items that depend on it
        </li>
      </ul>
    </div>
  );
}
