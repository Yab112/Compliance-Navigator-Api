"use client";

import { useId, useMemo, useRef, useState } from "react";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import type { GraphNodeType, GraphView } from "@cn/core/types/admin";
import { NativeSelect } from "@/modules/shared/native-select";
import { GraphDiagram, GraphLegend, type GraphDiagramHandle } from "@/modules/graph/graph-diagram";
import { layoutGraph, relatives } from "@/modules/graph/graph-layout";
import { NODE_TYPES, NODE_TYPE_ORDER } from "@/modules/graph/graph-style";
import { NodePanel } from "@/modules/graph/node-panel";

const MAX_RESULTS = 8;

/** Search, filters, the pan/zoom diagram and the details panel for the selected item. */
export function GraphExplorer({ view, onEdit }: { view: GraphView; onEdit: (docId: string) => void }) {
  const uid = useId();
  const diagram = useRef<GraphDiagramHandle>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hidden, setHidden] = useState<Set<GraphNodeType>>(new Set());
  const [sector, setSector] = useState("");

  const byKey = useMemo(() => new Map(view.nodes.map((n) => [n.key, n])), [view]);
  const presentTypes = NODE_TYPE_ORDER.filter((t) => view.nodes.some((n) => n.type === t));
  const sectors = useMemo(
    () => view.nodes.filter((n) => n.type === "Sector").sort((a, b) => a.label.localeCompare(b.label)),
    [view],
  );

  // A sector keeps what that business needs: the sector, its extra documents and everything before them
  const filtered = useMemo<GraphView>(() => {
    let keep: Set<string> | null = null;
    if (sector) {
      const sectorKey = `Sector:${sector}`;
      const seeds = [sectorKey, ...view.nodes.filter((n) => n.sectors?.includes(sector)).map((n) => n.key)];
      keep = new Set(seeds);
      for (const s of seeds) relatives(view, s).prereqs.forEach((k) => keep!.add(k));
    }
    const nodes = view.nodes.filter((n) => !hidden.has(n.type) && (!keep || keep.has(n.key)));
    const keys = new Set(nodes.map((n) => n.key));
    return { ...view, nodes, edges: view.edges.filter((e) => keys.has(e.source) && keys.has(e.target)) };
  }, [view, hidden, sector]);

  const layout = useMemo(() => layoutGraph(filtered), [filtered]);
  const visible = selectedKey && filtered.nodes.some((n) => n.key === selectedKey) ? selectedKey : null;
  const rel = useMemo(() => (visible ? relatives(filtered, visible) : null), [filtered, visible]);
  const highlight = useMemo(() => (rel ? { prereqs: rel.prereqs, dependants: rel.dependants } : null), [rel]);

  const q = query.trim().toLowerCase();
  const results = useMemo(
    () =>
      q
        ? filtered.nodes.filter(
            (n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q) || n.label_am?.includes(query.trim()),
          )
        : [],
    [filtered, q, query],
  );
  const matches = useMemo(() => new Set(results.map((n) => n.key)), [results]);

  const select = (key: string) => {
    setSelectedKey(key);
    diagram.current?.centerOn(key);
  };

  const toggleType = (t: GraphNodeType) =>
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });

  const selectedNode = visible ? byKey.get(visible) : undefined;

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
        <div className="relative flex flex-col gap-1.5">
          <Label htmlFor={`${uid}-search`}>Find an item</Label>
          <Input
            id={`${uid}-search`}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && results[0]) {
                e.preventDefault();
                select(results[0].key);
              }
            }}
            placeholder="e.g. TIN, passport, lease"
            aria-describedby={`${uid}-search-count`}
            autoComplete="off"
          />
          <p id={`${uid}-search-count`} className="text-muted-foreground text-[11px]" aria-live="polite">
            {q ? `${results.length} match${results.length === 1 ? "" : "es"}, outlined in the graph. Press Enter for the first.` : "Type to search names."}
          </p>
          {q && results.length > 0 && (
            <ul className="border-border bg-background max-h-56 overflow-y-auto border text-xs" aria-label="Matches">
              {results.slice(0, MAX_RESULTS).map((n) => (
                <li key={n.key}>
                  <button
                    type="button"
                    className="hover:bg-muted focus-visible:bg-muted w-full px-2 py-1.5 text-left outline-none"
                    onClick={() => select(n.key)}
                  >
                    {n.label} <span className="text-muted-foreground">· {NODE_TYPES[n.type].label}</span>
                  </button>
                </li>
              ))}
              {results.length > MAX_RESULTS && (
                <li className="text-muted-foreground px-2 py-1.5">{results.length - MAX_RESULTS} more, type more to narrow down</li>
              )}
            </ul>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${uid}-sector`}>Business sector</Label>
          <NativeSelect id={`${uid}-sector`} value={sector} onChange={(e) => setSector(e.target.value)} className="md:w-56">
            <option value="">All sectors</option>
            {sectors.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}: what it needs
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <legend className="text-muted-foreground mb-1 text-[11px]">Show</legend>
        {presentTypes.map((t) => (
          <label key={t} className="flex items-center gap-1.5">
            <input type="checkbox" checked={!hidden.has(t)} onChange={() => toggleType(t)} />
            {NODE_TYPES[t].plural}
            <span className="text-muted-foreground tabular-nums">({view.nodes.filter((n) => n.type === t).length})</span>
          </label>
        ))}
      </fieldset>

      <p className="text-muted-foreground text-[11px]" aria-live="polite">
        Showing {filtered.nodes.length} of {view.nodes.length} items and {filtered.edges.length} links.
        {filtered.nodes.length < view.nodes.length && " Hidden items also hide the links that pass through them."}
      </p>

      {filtered.nodes.length === 0 ? (
        <p className="border-border text-muted-foreground border border-dashed px-4 py-10 text-center text-xs">
          Nothing matches these filters. Tick more kinds of item above.
        </p>
      ) : (
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="min-w-0">
            <GraphDiagram
              ref={diagram}
              layout={layout}
              selectedKey={visible}
              highlight={highlight}
              matches={matches}
              onSelect={setSelectedKey}
            />
          </div>
          {selectedNode && rel ? (
            <NodePanel
              node={selectedNode}
              byKey={byKey}
              mesob={view.mesobLinks}
              rel={rel}
              onSelect={select}
              onEdit={onEdit}
              onClose={() => setSelectedKey(null)}
            />
          ) : (
            <div className="border-border text-muted-foreground hidden border border-dashed p-3 text-xs lg:block">
              Click an item, or find it with the search box, to see what it is, what it costs, how fresh the data is,
              what is needed before it and what depends on it.
            </div>
          )}
        </div>
      )}

      <GraphLegend layout={layout} />
    </div>
  );
}
