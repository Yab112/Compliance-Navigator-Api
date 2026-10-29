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
  DataSource,
  DataSourceRun,
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

export const useAdminOverview = () => useAdminQuery<AdminOverview>(["overview"], p.overview);

export const useDataSources = (poll: boolean) =>
  useAdminQuery<{ sources: DataSource[] }>(["data-sources"], p.dataSources, {
    refetchInterval: poll ? 3000 : false,
  });

export const DATA_SOURCE_RUNS_PAGE_SIZE = 20;

export type DataSourceRunFilters = { source?: string; status?: string; from?: string; to?: string; page?: number };

export const useDataSourceRuns = (filters: DataSourceRunFilters, poll: boolean) => {
  const { source = "", status = "", from = "", to = "", page = 0 } = filters;
  const params = new URLSearchParams({
    limit: String(DATA_SOURCE_RUNS_PAGE_SIZE),
    offset: String(page * DATA_SOURCE_RUNS_PAGE_SIZE),
  });
  if (source) params.set("source", source);
  if (status) params.set("status", status);
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  return useAdminQuery<Paged<DataSourceRun>>(
    ["data-source-runs", source, status, from, to, page],
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
  const { run, isPending } = useAdminMutation<{ run: DataSourceRun }, undefined>();
  return { runSource: (id: string) => run(p.runDataSource(id), MTD.POST), isPending };
};

/** Pause stops both "Run now" and the schedule; resume turns them back on. */
export const usePauseDataSource = () => {
  const { run, isPending } = useAdminMutation<{ source: string; enabled: boolean }, undefined>();
  return {
    setPaused: (id: string, paused: boolean) =>
      run(paused ? p.pauseDataSource(id) : p.resumeDataSource(id), MTD.POST),
    isPending,
  };
};

export const useMarkRunFailed = () => {
  const { run, isPending } = useAdminMutation<{ run: DataSourceRun }, undefined>();
  return { markFailed: (runId: string) => run(p.markRunFailed(runId), MTD.POST), isPending };
};

/** One staff-added source with its pasted text, for the edit form. */
export const useCustomDataSource = (id: string | null) =>
  useAdminQuery<{ source: CustomDataSource }>(["custom-data-source", id], p.customDataSource(id ?? ""), {
    enabled: !!id,
  });

export const useSaveCustomDataSource = () => {
  const { run, isPending } = useAdminMutation<{ source: CustomDataSource; key?: string }, CustomDataSourceInput>();
  return {
    save: (id: string | null, body: CustomDataSourceInput) =>
      id ? run(p.customDataSource(id), MTD.PUT, body) : run(p.customDataSources, MTD.POST, body),
    isPending,
  };
};

export const useDeleteCustomDataSource = () => {
  const { run, isPending } = useAdminMutation<{ deleted: { id: string; name: string; chunks_removed: number } }, undefined>();
  return { remove: (id: string) => run(p.customDataSource(id), MTD.DELETE), isPending };
};

export const useGraphStats = () => useAdminQuery<GraphCounts>(["graph-stats"], p.graphStats);
export const useGraphView = () => useAdminQuery<GraphView>(["graph-view"], p.graphView);
export const useGraphDocuments = () =>
  useAdminQuery<{ documents: GraphDocument[] }>(["graph-documents"], p.graphDocuments);
export const useGraphInstitutions = () =>
  useAdminQuery<{ institutions: InstitutionBreakdown[] }>(["graph-institutions"], p.graphInstitutions);

export type DocumentPatch = Partial<
  Pick<
    GraphDocument,
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
  const { run, isPending } = useAdminMutation<{ document: GraphDocument }, DocumentPatch>();
  return { updateDocument: (id: string, body: DocumentPatch) => run(p.graphDocument(id), MTD.PATCH, body), isPending };
};

export const useCypherQuery = () => {
  const { run, isPending } = useAdminMutation<{ rows: Record<string, unknown>[]; count: number }, { query: string }>();
  return { runQuery: (query: string) => run(p.graphQuery, MTD.POST, { query }), isPending };
};

export const useAIStatus = () => useAdminQuery<AIStatus>(["ai-status"], p.aiStatus);

export const useSaveAISettings = () => {
  const { run, isPending } = useAdminMutation<
    { provider: string; ollama_model: string },
    { provider: string; ollama_model?: string }
  >();
  return { saveSettings: (body: { provider: string; ollama_model?: string }) => run(p.aiSettings, MTD.PUT, body), isPending };
};

export const useAITest = () => {
  const { run, isPending } = useAdminMutation<AITestResult, { message: string }>();
  return { testPrompt: (message: string) => run(p.aiTest, MTD.POST, { message }), isPending };
};

export const useKnowledgeSearch = () => {
  const { run, isPending } = useAdminMutation<{ results: KnowledgeHit[] }, { query: string; limit: number }>();
  return { search: (query: string) => run(p.aiSearch, MTD.POST, { query, limit: 8 }), isPending };
};

export const FEEDBACK_PAGE_SIZE = 25;

export const useFeedbackFlags = (status: string, page = 0) =>
  useAdminQuery<{ flags: FeedbackFlag[]; total: number }>(
    ["feedback", status, page],
    `${p.feedback}?status=${encodeURIComponent(status)}&limit=${FEEDBACK_PAGE_SIZE}&offset=${page * FEEDBACK_PAGE_SIZE}`,
  );

export const useResolveFlag = () => {
  const { run, isPending } = useAdminMutation<{ flag: FeedbackFlag }, { status: string; note?: string }>();
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
  const { run, isPending } = useAdminMutation<{ user: AdminUser }, { role?: string; is_active?: boolean }>();
  return {
    updateUser: (id: string, body: { role?: string; is_active?: boolean }) => run(p.user(id), MTD.PATCH, body),
    isPending,
  };
};

export const useAuthSummary = () => useAdminQuery<AuthSummary>(["auth", "summary"], p.authSummary);

export const AUTH_EVENTS_PAGE_SIZE = 25;

export const useAuthEvents = (userId?: string, page = 0) => {
  const params = new URLSearchParams({
    limit: String(AUTH_EVENTS_PAGE_SIZE),
    offset: String(page * AUTH_EVENTS_PAGE_SIZE),
  });
  if (userId) params.set("user_id", userId);
  return useAdminQuery<{ events: AuthEvent[]; total: number }>(
    ["auth", "events", userId ?? "all", page],
    `${p.authEvents}?${params}`,
  );
};

export const useUserSecurityActions = () => {
  const { run, isPending } = useAdminMutation<{ signedOut?: number; link?: string; expiresInMinutes?: number }, undefined>();
  return {
    revokeSessions: (id: string) => run(p.userRevokeSessions(id), MTD.POST),
    issueResetLink: (id: string) => run(p.userResetLink(id), MTD.POST),
    isPending,
  };
};
