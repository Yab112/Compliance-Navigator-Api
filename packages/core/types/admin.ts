import type { User } from "./user-types";
import type { CatalogStats } from "./catalog";
import type { GudayStats } from "./guday";

export type DataSourceRun = {
  id: string;
  source: string;
  status: "running" | "success" | "failed";
  stats: Record<string, unknown>;
  error?: string | null;
  triggered_by?: string | null;
  started_at: string;
  finished_at?: string | null;
  duration_s?: number;
  /** Readable source name; "Deleted source" for a staff-added source that was removed */
  source_label?: string;
};

export type DataSourceKind = "scraper" | "graph" | "rag" | "maintenance" | "web_page" | "pasted_text";
export type DataSourceSchedule = "manual" | "daily" | "weekly";
/** Where a source's data ends up */
export type DataSourceDestination = "catalog" | "graph" | "knowledge" | "records";

/** A source staff added from the admin app (stored in the database, not in code). */
export type CustomDataSource = {
  id: string;
  name: string;
  description: string;
  kind: "web_page" | "pasted_text";
  url: string | null;
  issuing_body: string | null;
  language: "en" | "am";
  tags: string[];
  schedule: DataSourceSchedule;
  enabled: boolean;
  paused_by: string | null;
  paused_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_by: string | null;
  updated_at: string;
  text_length: number;
  /** Passages it currently has in the AI knowledge base (list only) */
  passages?: number;
  /** Pasted document text (single-source fetch only) */
  text?: string | null;
};

export type CustomDataSourceInput = {
  name: string;
  description: string;
  kind: "web_page" | "pasted_text";
  url: string | null;
  text: string | null;
  issuing_body: string | null;
  language: "en" | "am";
  tags: string[];
  schedule: DataSourceSchedule;
  enabled: boolean;
};

export type DataSource = {
  /** Pipeline key, or "custom:<uuid>" for staff-added sources */
  id: string;
  label: string;
  description: string;
  kind: DataSourceKind;
  url?: string | null;
  builtIn: boolean;
  schedule: DataSourceSchedule;
  destinations: DataSourceDestination[];
  /** false when paused: it can't be run by hand or by the schedule */
  enabled: boolean;
  pausedBy: string | null;
  pausedAt: string | null;
  custom: CustomDataSource | null;
  lastRun: DataSourceRun | null;
  successes: number;
  failures: number;
  lastSuccessAt?: string | null;
  health: DataSourceHealth;
};

/** Reliability over the last `windowDays`; the "last" fields look at all history. */
export type DataSourceHealth = {
  windowDays: number;
  runs: number;
  successes: number;
  failures: number;
  /** 0..1 over finished runs, null when nothing finished in the window */
  successRate: number | null;
  avgDurationS: number | null;
  lastDurationS: number | null;
  lastSuccessAt: string | null;
  lastFailureAt: string | null;
  lastFailureError: string | null;
  daily: { day: string; success: number; failed: number }[];
};

export type GraphCounts = {
  nodes: Record<string, number>;
  relationships: Record<string, number>;
  totalNodes: number;
  totalRelationships: number;
  staleDocuments: number;
};

export type GraphNode = {
  id: string;
  label: string;
  type: "Service" | "Document" | "Sector";
  stale?: boolean | null;
  fee?: number | null;
  days?: number | null;
};

export type GraphView = {
  nodes: GraphNode[];
  edges: { source: string; target: string; type: "REQUIRES" | "TARGETS" | "SECTOR_EXTRA" }[];
  mesobLinks: { document: string; id: string; name: string; institution?: string | null }[];
};

export type GraphDocument = {
  id: string;
  name: string;
  name_am?: string | null;
  issuing_authority?: string;
  form_code?: string | null;
  fee_etb?: number | null;
  avg_processing_days?: number | null;
  legal_basis?: string | null;
  source_url?: string | null;
  required_input_labels?: string[];
  rejection_reasons?: string[];
  last_verified?: string | null;
  stale?: boolean;
  prerequisites: string[];
  mesob_services: { id: string; name: string }[];
  target_of: string[];
};

export type InstitutionBreakdown = {
  id: string;
  name: string;
  short_name?: string | null;
  services: number;
  avg_minutes?: number | null;
  online: number;
};

export type AIStatus = {
  provider: "ollama" | "anthropic" | "keyword";
  providers: string[];
  ollama: {
    baseUrl: string;
    reachable: boolean;
    model: string;
    models: string[];
    modelInstalled: boolean;
  };
  anthropic: { configured: boolean };
  embeddings: { model: string; dimension: number };
  speechToText: { engine: string; model: string };
  knowledgeBase: {
    total?: number;
    mesob?: number;
    sources?: number;
    last_ingested_at?: string | null;
    error?: string;
  };
};

export type AITestResult = {
  provider: string;
  latencyMs: number;
  reply: string;
  intent: string;
  language: string;
  suggestedGoal?: string | null;
  suggestedSubCity?: string | null;
  catalogMatches: { id: string; name: string; institution: string }[];
  roadmapBuilt: boolean;
};

export type KnowledgeHit = {
  id: string;
  content: string;
  similarity: number;
  service_id?: string | null;
  document_id?: string | null;
  issuing_body?: string | null;
  source_url?: string | null;
};

export type AdminUser = Required<Pick<User, "id" | "email" | "fullname">> & {
  role: "user" | "agent" | "admin";
  phone?: string | null;
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
  active_sessions?: number;
};

export type AuthSummary = {
  signed_in_users: number;
  active_sessions: number;
  failed_logins_24h: number;
  blocked_24h: number;
  token_reuse_7d: number;
  registrations_7d: number;
};

export type FeedbackFlag = {
  id: string;
  user_email?: string | null;
  target_type: string;
  target_id?: string | null;
  message: string;
  status: "open" | "resolved" | "dismissed";
  resolution_note?: string | null;
  resolved_by?: string | null;
  created_at: string;
  resolved_at?: string | null;
};

export type DayCount = { day: string; count: number };

export type AdminOverview = {
  users: { total: number; new_30d: number; admins: number; agents: number };
  roadmaps: { total: number; last_30d: number; users: number };
  roadmapsByDay: DayCount[];
  roadmapsByGoal: { goal: string; count: number }[];
  casesByDay: DayCount[];
  guday: GudayStats;
  organizations: OrgAdminCounts | { error: string };
  catalog: CatalogStats;
  graph: GraphCounts | { error: string };
  ai: AIStatus | { error: string };
  openFlags: number;
  dataSources: DataSource[];
};

export type OrgAdminCounts = {
  organizations: number;
  verified: number;
  pending_orgs: number;
  pending_submissions: number;
  live_services: number;
};
