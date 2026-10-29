"use client";

import { useMemo } from "react";
import { ChartTheme } from "@cn/ui/charts/chart-theme";
import type { GraphView } from "@cn/core/types/admin";
import { NODE_H, NODE_W, edgePath, layoutGraph, type PlacedNode } from "@/modules/graph/graph-layout";

const EDGE_STYLE = {
  REQUIRES: { color: "var(--viz-series-1)", label: "Requires (prerequisite → document)" },
  TARGETS: { color: "var(--viz-series-2)", label: "Targets (service → final document)" },
  SECTOR_EXTRA: { color: "var(--viz-series-3)", label: "Sector extra requirement" },
} as const;

const TYPE_LABEL = { Service: "Service", Document: "Document", Sector: "Sector" } as const;

function truncate(text: string, max = 22) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

type GraphDiagramProps = {
  view: GraphView;
  selectedKey: string | null;
  onSelect: (node: PlacedNode | null) => void;
};

export function GraphDiagram({ view, selectedKey, onSelect }: GraphDiagramProps) {
  const layout = useMemo(() => layoutGraph(view), [view]);

  return (
    <div className="viz-root">
      <ChartTheme />
      <ul className="text-muted-foreground mb-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
        {Object.entries(EDGE_STYLE).map(([type, s]) => (
          <li key={type} className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded" style={{ background: s.color }} />
            {s.label}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span className="size-2.5 ring-2 ring-amber-500" /> ▲ Stale (not verified in 30 days)
        </li>
        <li className="flex items-center gap-1.5">
          <span className="bg-primary/15 text-primary px-1 text-[9px] font-medium">MESOB</span> Doable at a MESOB center
        </li>
      </ul>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          width="100%"
          // Scale down to fit the panel; scroll instead once nodes would get unreadable
          style={{ minWidth: Math.min(layout.width, 720), maxWidth: layout.width }}
          className="h-auto"
          role="img"
          aria-label="Compliance dependency graph: services, required documents and sector extras"
          onClick={() => onSelect(null)}
        >
          <defs>
            {Object.entries(EDGE_STYLE).map(([type, s]) => (
              <marker key={type} id={`arrow-${type}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L8,4 L0,8 z" fill={s.color} />
              </marker>
            ))}
          </defs>
          {layout.edges.map((e) => {
            const dim = selectedKey && e.from.key !== selectedKey && e.to.key !== selectedKey;
            return (
              <path
                key={e.key}
                d={edgePath(e)}
                fill="none"
                stroke={EDGE_STYLE[e.type].color}
                strokeWidth={2}
                opacity={dim ? 0.15 : 0.85}
                markerEnd={`url(#arrow-${e.type})`}
              />
            );
          })}
          {layout.nodes.map((n) => {
            const selected = n.key === selectedKey;
            const stale = n.type === "Document" && n.stale;
            return (
              <g
                key={n.key}
                transform={`translate(${n.x},${n.y})`}
                className="cursor-pointer"
                onClick={(ev) => {
                  ev.stopPropagation();
                  onSelect(selected ? null : n);
                }}
              >
                <title>
                  {`${TYPE_LABEL[n.type]}: ${n.label}${stale ? " (stale)" : ""}${n.mesobCount ? ` · ${n.mesobCount} MESOB service(s)` : ""}`}
                </title>
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  className={n.type === "Document" ? "fill-card" : "fill-muted"}
                  stroke={selected ? "var(--primary)" : stale ? "#d97706" : "var(--border)"}
                  strokeWidth={selected || stale ? 2 : 1}
                />
                <text x={8} y={15} className="fill-muted-foreground text-[9px] uppercase tracking-wide">
                  {TYPE_LABEL[n.type]}
                  {stale ? " · ▲ stale" : ""}
                </text>
                <text x={8} y={31} className="fill-foreground text-[11px] font-medium">
                  {truncate(n.label)}
                </text>
                {n.mesobCount > 0 && (
                  <g transform={`translate(${NODE_W - 50},${NODE_H - 13})`}>
                    <rect width={44} height={11} className="fill-primary/15" />
                    <text x={22} y={8.5} textAnchor="middle" className="fill-primary text-[8px] font-semibold">
                      MESOB ×{n.mesobCount}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
