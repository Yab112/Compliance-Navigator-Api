import type { GraphEdgeType, GraphNodeType } from "@cn/core/types/admin";

/** How each kind of node is named and coloured in the diagram, its legend and the details panel. */
export const NODE_TYPES: Record<GraphNodeType, { label: string; plural: string; color: string; about: string }> = {
  Document: {
    label: "Document",
    plural: "Documents",
    color: "var(--primary)",
    about: "A paper or certificate a citizen has to get from a government office, such as a Kebele ID or a TIN certificate.",
  },
  Service: {
    label: "Goal",
    plural: "Goals",
    color: "var(--viz-series-3)",
    about: "Something a citizen asks for in the app, such as a passport or a trade license. Its roadmap ends at the document it needs.",
  },
  Sector: {
    label: "Business sector",
    plural: "Business sectors",
    color: "var(--viz-series-4)",
    about: "A line of business, such as fintech, that needs extra permits on top of the usual business documents.",
  },
  OrgService: {
    label: "Organization service",
    plural: "Organization services",
    color: "var(--viz-series-1)",
    about: "A service an onboarded organization published on the platform, with its own requirements.",
  },
  OrgDocument: {
    label: "Organization requirement",
    plural: "Organization requirements",
    color: "var(--muted-foreground)",
    about: "A requirement an organization typed in that is not yet matched to a document in the graph.",
  },
};

export const NODE_TYPE_ORDER: GraphNodeType[] = ["Document", "Service", "Sector", "OrgService", "OrgDocument"];

/** Edges point from what must happen first to what depends on it. */
export const EDGE_TYPES: Record<GraphEdgeType, { label: string; color: string; dashed?: boolean }> = {
  REQUIRES: { label: "Needed before the next document", color: "var(--muted-foreground)" },
  TARGETS: { label: "Final document of a goal", color: "var(--viz-series-3)" },
  SECTOR_EXTRA: { label: "Extra document for a sector", color: "var(--viz-series-4)" },
  ORG_REQUIRES: { label: "Asked for by an organization service", color: "var(--viz-series-1)", dashed: true },
  ISSUES: { label: "Handed out by an organization service", color: "var(--viz-series-1)" },
  PREREQUISITE: { label: "Organization service needed first", color: "var(--viz-series-1)", dashed: true },
};

export const HIGHLIGHT = {
  prereq: "var(--viz-series-1)",
  dependant: "var(--viz-series-2)",
  stale: "#d97706",
} as const;

export function formatFee(fee: number | null | undefined) {
  if (fee == null) return "Fee unknown";
  return fee === 0 ? "Free" : `${fee.toLocaleString("en")} ETB`;
}

export function formatDuration(days: number | null | undefined, minutes?: number | null) {
  if (days != null) return `${days} day${days === 1 ? "" : "s"}`;
  if (minutes != null) return minutes < 60 ? `${minutes} min` : `${Math.round(minutes / 60)} h`;
  return "Time unknown";
}
