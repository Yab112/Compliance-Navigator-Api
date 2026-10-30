"use client";

import { apiPaths } from "../../lib/constants/api-paths";
import { MTD } from "../../lib/constants/methods";
import type {
  AdminOverview,
  AdminUser,
  AIStatus,
  AITestResult,
  AuthSummary,
  CustomDataSource,
  CustomDataSourceInput,
  CypherResult,
  DataSource,
  DataSourceRun,
  FeedbackFilters,
  FeedbackFlag,
  GraphCounts,
  GraphDocument,
  GraphView,
  InstitutionBreakdown,
  KnowledgeHit,
} from "../../types/admin";
import type { Paged } from "../../types/guday";
import type { AuthEvent } from "../../types/user-types";
import { useAdminMutation, useAdminQuery } from "./use-admin-query";

export { useAdminMutation, useAdminQuery };

const p = apiPaths.admin;

// Running or editing a data source changes its runs, the graph it feeds and the overview counts
const DATA_SOURCE_KEYS = [["data-sources"], ["data-source-runs"], ["custom-data-source"], ["graph-stats"], ["overview"]];
const GRAPH_KEYS = [["graph-document"], ["graph-documents"], ["graph-stats"], ["graph-view"], ["graph-institutions"]];

export const useAdminOverview = () => useAdminQuery<AdminOverview>(["overview"], p.overview);

export const useDataSources = (poll: boolean) =>
  useAdminQuery<{ sources: DataSource[] }>(["data-sources"], p.dataSources, {
    refetchInterval: poll ? 3000 : false,
  });

export const DATA_SOURCE_RUNS_PAGE_SIZE = 20;

export type DataSourceRunFilters = { source?: string; status?: string; from?: string; to?: string; page?: number; size?: number };

export const useDataSourceRuns = (filters: DataSourceRunFilters, poll: boolean) => {
  const { source = "", status = "", from = "", to = "", page = 0, size = DATA_SOURCE_RUNS_PAGE_SIZE } = filters;
  const params = new URLSearchParams({
    limit: String(size),
    offset: String(page * size),
  });
  if (source) params.set("source", source);
  if (status) params.set("status", status);
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  return useAdminQuery<Paged<DataSourceRun>>(
    ["data-source-runs", source, status, from, to, page, size],
    `${p.dataSourceRuns}?${params}`,
    { refetchInterval: poll ? 3000 : false },
  );
};

/** Total number of runs ever recorded, for the tab label. */
export const useDataSourceRunTotal = (poll: boolean) =>
  useAdminQuery<Paged<DataSourceRun>>(["data-source-runs", "total"], `${p.dataSourceRuns}?limit=1`, {
    refetchInterval: poll ? 3000 : false,
  }).payload?.total;

export const useRunDataSource = () => {
  const { run, isPending } = useAdminMutation<{ run: DataSourceRun }, undefined>(DATA_SOURCE_KEYS);
  return { runSource: (id: string) => run(p.runDataSource(id), MTD.POST), isPending };
};

/** Pause stops both "Run now" and the schedule; resume turns them back on. */
export const usePauseDataSource = () => {
  const { run, isPending } = useAdminMutation<{ source: string; enabled: boolean }, undefined>(DATA_SOURCE_KEYS);
  return {
    setPaused: (id: string, paused: boolean) =>
      run(paused ? p.pauseDataSource(id) : p.resumeDataSource(id), MTD.POST),
    isPending,
  };
};

export const useMarkRunFailed = () => {
  const { run, isPending } = useAdminMutation<{ run: DataSourceRun }, undefined>(DATA_SOURCE_KEYS);
  return { markFailed: (runId: string) => run(p.markRunFailed(runId), MTD.POST), isPending };
};

/** One staff-added source with its pasted text, for the edit form. */
export const useCustomDataSource = (id: string | null) =>
  useAdminQuery<{ source: CustomDataSource }>(["custom-data-source", id], p.customDataSource(id ?? ""), {
    enabled: !!id,
  });

export const useSaveCustomDataSource = () => {
  const { run, isPending } = useAdminMutation<{ source: CustomDataSource; key?: string }, CustomDataSourceInput>(DATA_SOURCE_KEYS);
  return {
    save: (id: string | null, body: CustomDataSourceInput) =>
      id ? run(p.customDataSource(id), MTD.PUT, body) : run(p.customDataSources, MTD.POST, body),
    isPending,
  };
};

export const useDeleteCustomDataSource = () => {
  const { run, isPending } = useAdminMutation<{ deleted: { id: string; name: string; chunks_removed: number } }, undefined>(DATA_SOURCE_KEYS);
  return { remove: (id: string) => run(p.customDataSource(id), MTD.DELETE), isPending };
};

export const useGraphStats = () => useAdminQuery<GraphCounts>(["graph-stats"], p.graphStats);
export const useGraphView = () => useAdminQuery<GraphView>(["graph-view"], p.graphView);
export const GRAPH_DOCUMENTS_PAGE_SIZE = 20;

export const useGraphDocuments = (filters: { q?: string; status?: string; page?: number; size?: number }) => {
  const { q = "", status = "", page = 0, size = GRAPH_DOCUMENTS_PAGE_SIZE } = filters;
  const params = new URLSearchParams({
    limit: String(size),
    offset: String(page * size),
  });
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  return useAdminQuery<Paged<GraphDocument>>(["graph-documents", q, status, page, size], `${p.graphDocuments}?${params}`);
};

export const GRAPH_INSTITUTIONS_PAGE_SIZE = 15;

export const useGraphInstitutions = (filters: { q?: string; page?: number; size?: number }) => {
  const { q = "", page = 0, size = GRAPH_INSTITUTIONS_PAGE_SIZE } = filters;
  const params = new URLSearchParams({
    limit: String(size),
    offset: String(page * size),
  });
  if (q) params.set("q", q);
  return useAdminQuery<Paged<InstitutionBreakdown>>(["graph-institutions", q, page, size], `${p.graphInstitutions}?${params}`);
};

export type DocumentPatch = Partial<
  Pick<
    GraphDocument,
    | "name"
    | "name_am"
    | "form_code"
    | "fee_etb"
    | "avg_processing_days"
    | "legal_basis"
    | "source_url"
    | "issuing_authority"
    | "required_input_labels"
    | "rejection_reasons"
  >
> & { mark_verified?: boolean };

export const useUpdateDocument = () => {
  const { run, isPending } = useAdminMutation<{ document: GraphDocument }, DocumentPatch>(GRAPH_KEYS);
  return { updateDocument: (id: string, body: DocumentPatch) => run(p.graphDocument(id), MTD.PATCH, body), isPending };
};

export const useCypherQuery = () => {
  const { run, isPending } = useAdminMutation<CypherResult, { query: string }>("none");
  return { runQuery: (query: string) => run(p.graphQuery, MTD.POST, { query }), isPending };
};

export const useAIStatus = () => useAdminQuery<AIStatus>(["ai-status"], p.aiStatus);

export const useSaveAISettings = () => {
  const { run, isPending } = useAdminMutation<
    { provider: string; ollama_model: string },
    { provider: string; ollama_model?: string }
  >([["ai-status"]]);
  return { saveSettings: (body: { provider: string; ollama_model?: string }) => run(p.aiSettings, MTD.PUT, body), isPending };
};

export const useAITest = () => {
  const { run, isPending } = useAdminMutation<AITestResult, { message: string }>("none");
  return { testPrompt: (message: string) => run(p.aiTest, MTD.POST, { message }), isPending };
};

export const useKnowledgeSearch = () => {
  const { run, isPending } = useAdminMutation<{ results: KnowledgeHit[] }, { query: string; limit: number }>("none");
  return { search: (query: string) => run(p.aiSearch, MTD.POST, { query, limit: 8 }), isPending };
};

export const FEEDBACK_PAGE_SIZE = 25;

export const useFeedbackFlags = (filters: FeedbackFilters, page = 0, size = FEEDBACK_PAGE_SIZE) => {
  const params = new URLSearchParams({ status: filters.status, limit: String(size), offset: String(page * size) });
  if (filters.target_type) params.set("target_type", filters.target_type);
  if (filters.q) params.set("q", filters.q);
  if (filters.org_id) params.set("org_id", filters.org_id);
  return useAdminQuery<{ flags: FeedbackFlag[]; total: number }>(["feedback", filters, page, size], `${p.feedback}?${params}`);
};

export const useResolveFlag = () => {
  const { run, isPending } = useAdminMutation<{ flag: FeedbackFlag }, { status: string; note?: string }>([["feedback"], ["overview"]]);
  return {
    resolveFlag: (id: string, status: string, note?: string) => run(p.feedbackItem(id), MTD.PATCH, { status, note }),
    isPending,
  };
};

export const useAdminUsers = (q: string, role: string, page: number, pageSize: number) => {
  const params = new URLSearchParams({ limit: String(pageSize), offset: String(page * pageSize) });
  if (q) params.set("q", q);
  if (role) params.set("role", role);
  return useAdminQuery<Paged<AdminUser>>(["users", q, role, page, pageSize], `${p.users}?${params}`);
};

export const useUpdateUser = () => {
  const { run, isPending } = useAdminMutation<{ user: AdminUser }, { role?: string; is_active?: boolean }>([["users"], ["auth"], ["overview"]]);
  return {
    updateUser: (id: string, body: { role?: string; is_active?: boolean }) => run(p.user(id), MTD.PATCH, body),
    isPending,
  };
};

export const useAuthSummary = () => useAdminQuery<AuthSummary>(["auth", "summary"], p.authSummary);

export const AUTH_EVENTS_PAGE_SIZE = 25;

export const useAuthEvents = (userId?: string, page = 0, size = AUTH_EVENTS_PAGE_SIZE) => {
  const params = new URLSearchParams({
    limit: String(size),
    offset: String(page * size),
  });
  if (userId) params.set("user_id", userId);
  return useAdminQuery<{ events: AuthEvent[]; total: number }>(
    ["auth", "events", userId ?? "all", page, size],
    `${p.authEvents}?${params}`,
  );
};

export const useUserSecurityActions = () => {
  const { run, isPending } = useAdminMutation<{ signedOut?: number; link?: string | null; emailed?: boolean; expiresInMinutes?: number }, undefined>([["users"], ["auth"]]);
  return {
    revokeSessions: (id: string) => run(p.userRevokeSessions(id), MTD.POST),
    issueResetLink: (id: string) => run(p.userResetLink(id), MTD.POST),
    isPending,
  };
};
