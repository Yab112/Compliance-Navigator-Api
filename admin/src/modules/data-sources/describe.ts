import { humanize } from "@cn/core/lib/format";
import type {
  DataSource,
  DataSourceDestination,
  DataSourceHealth,
  DataSourceKind,
  DataSourceRun,
} from "@cn/core/types/admin";

/** Same limit the server uses before a "running" run counts as stuck. */
export const STUCK_AFTER_MINUTES = 30;

export const KIND_LABEL: Record<DataSourceKind, string> = {
  scraper: "Website reader",
  graph: "Graph update",
  rag: "AI knowledge",
  maintenance: "Housekeeping",
  web_page: "Web page",
  pasted_text: "Pasted text",
};

export const DESTINATIONS: Record<DataSourceDestination, { label: string; help: string }> = {
  catalog: { label: "Service catalog", help: "the list of government services citizens browse and search" },
  graph: {
    label: "Knowledge graph",
    help: "the map of services, documents, offices and how they depend on each other; roadmaps are built from it",
  },
  knowledge: {
    label: "AI knowledge base",
    help: "short passages the AI assistant searches and quotes, with a link to where they came from",
  },
  records: { label: "Agent and organization records", help: "license and listing status on the marketplace" },
};

export const percent = (rate: number | null) => (rate == null ? "-" : `${Math.round(rate * 100)}%`);
export const firstLine = (text: string) => text.split("\n").find((l) => l.trim()) ?? text;
const n = (v: unknown) => Number(v ?? 0).toLocaleString("en");
const plural = (count: unknown, one: string, many = `${one}s`) => `${n(count)} ${Number(count) === 1 ? one : many}`;

/** Failing when the most recent finished run failed. */
export function isFailing(h: DataSourceHealth) {
  return !!h.lastFailureAt && (!h.lastSuccessAt || h.lastFailureAt > h.lastSuccessAt);
}

/** A run still "running" after the limit almost certainly died (server restart or crash). */
export function isStuck(run: DataSourceRun | null | undefined) {
  if (!run || run.status !== "running") return false;
  return Date.now() - new Date(run.started_at).getTime() > STUCK_AFTER_MINUTES * 60_000;
}

/** Element id for a source card, so other parts of the page can link to it. */
export const cardId = (sourceId: string) => `source-${sourceId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;

export function scheduleText(source: DataSource): { text: string; note?: string } {
  if (source.schedule === "manual") return { text: "Only when you press Run now" };
  const when = source.schedule === "daily" ? "once a day" : "once a week";
  if (source.builtIn) {
    return {
      text: source.id === "mesob_catalog" ? "Automatically every night" : `Automatically ${when}`,
      note: "Needs the background worker and its scheduler to be running on the server.",
    };
  }
  return {
    text: `Automatically ${when}`,
    note: `Checked every hour; it runs when a ${source.schedule === "daily" ? "day" : "week"} has passed since its last successful run. Needs the background worker and its scheduler to be running on the server.`,
  };
}

/** Plain sentences for what a successful run changed, built from its stats. */
export function describeChanges(stats: Record<string, unknown> | null | undefined): string[] {
  const s = stats ?? {};
  const out: string[] = [];
  const graph = (s.graph ?? (typeof s.document_links === "number" ? s : null)) as Record<string, unknown> | null;

  if (typeof s.characters_read === "number") {
    out.push(
      typeof s.pdf_pages === "number"
        ? `Read a ${plural(s.pdf_pages, "page")} PDF (${plural(s.characters_read, "character")})`
        : `Read ${plural(s.characters_read, "character")} of text`,
    );
  }
  if (typeof s.services === "number" && typeof s.institutions === "number" && s.source === "mesob") {
    out.push(
      `Found ${plural(s.services, "service")} from ${plural(s.institutions, "institution")} and ${plural(s.centers, "MESOB center")}`,
    );
  }
  if (graph) {
    let line = `Updated the knowledge graph with ${plural(graph.services, "service")}, ${plural(graph.institutions, "institution")} and ${plural(graph.centers, "center")}`;
    if (Number(graph.services_removed) > 0) line += `, and removed ${plural(graph.services_removed, "service")} no longer listed`;
    out.push(line);
  }
  if (typeof s.chunks_inserted === "number") {
    let line = `Added ${plural(s.chunks_inserted, "passage")} to the AI knowledge base`;
    if (typeof s.samples === "number") line += ` from ${plural(s.samples, "curated excerpt")}`;
    if (Number(s.chunks_removed) > 0) line += `, replacing ${n(s.chunks_removed)} older ones`;
    out.push(line);
  }
  if (typeof s.totalNodes === "number") {
    out.push(
      `The knowledge graph now holds ${plural(s.totalNodes, "item")} and ${plural(s.totalRelationships, "connection")}`,
    );
  }
  if (typeof s.stale === "number") {
    out.push(
      Number(s.stale) > 0
        ? `${n(s.stale)} of ${plural(s.checked, "document")} need re-checking (not verified since ${s.cutoff ?? "the cutoff"})`
        : `All ${plural(s.checked, "document")} were checked recently`,
    );
  }
  if (typeof s.agent_licenses_expired === "number" && s.agent_licenses_expired > 0) {
    out.push(`Suspended ${plural(s.agent_licenses_expired, "agent")} whose license expired`);
  }
  if (typeof s.org_changes_went_live === "number" && s.org_changes_went_live > 0) {
    out.push(`Put ${plural(s.org_changes_went_live, "scheduled organization change")} live`);
  }
  if (typeof s.org_services_due_for_confirmation === "number" && s.org_services_due_for_confirmation > 0) {
    out.push(`${plural(s.org_services_due_for_confirmation, "organization service")} waiting for the owner to confirm`);
  }
  const custom = s.custom_sources_refreshed as Record<string, number> | undefined;
  if (custom && custom.due > 0) {
    out.push(
      `Refreshed ${plural(custom.succeeded, "staff-added source")}${custom.failed ? ` (${n(custom.failed)} failed)` : ""}`,
    );
  }
  if (!out.length) {
    const parts = Object.entries(s)
      .filter(([, v]) => typeof v === "number")
      .slice(0, 3)
      .map(([k, v]) => `${n(v)} ${humanize(k).toLowerCase()}`);
    if (parts.length) out.push(parts.join(", "));
  }
  return out;
}

/** One line for a run in the history table. */
export function summarizeRun(run: DataSourceRun): string {
  if (run.status === "running") return isStuck(run) ? "Not responding (may be stuck)" : "In progress";
  if (run.error) return firstLine(run.error);
  return describeChanges(run.stats)[0] ?? "Finished, nothing to report";
}
