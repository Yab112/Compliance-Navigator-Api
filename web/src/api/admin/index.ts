"use client";

import { apiPaths } from "@/lib/constants/api-paths";
import { MTD } from "@/lib/constants/methods";
import type {
  AdminOverview,
  AdminUser,
  AIStatus,
  AITestResult,
  AuthSummary,
  DataSource,
  DataSourceRun,
  FeedbackFlag,
  GraphCounts,
  GraphDocument,
  GraphView,
  InstitutionBreakdown,
  KnowledgeHit,
} from "@/types/admin";
import type { Paged } from "@/types/guday";
import type { AuthEvent } from "@/types/user-types";
import { useAdminMutation, useAdminQuery } from "./use-admin-query";

export { useAdminMutation, useAdminQuery };

const p = apiPaths.admin;

export const useAdminOverview = () => useAdminQuery<AdminOverview>(["overview"], p.overview);

export const useDataSources = (poll: boolean) =>
  useAdminQuery<{ sources: DataSource[] }>(["data-sources"], p.dataSources, {
    refetchInterval: poll ? 3000 : false,
  });

export const useDataSourceRuns = (source: string | null, poll: boolean) =>
  useAdminQuery<{ runs: DataSourceRun[] }>(
    ["data-source-runs", source],
    source ? `${p.dataSourceRuns}?source=${encodeURIComponent(source)}&limit=100` : `${p.dataSourceRuns}?limit=100`,
    { refetchInterval: poll ? 3000 : false },
  );

export const useRunDataSource = () => {
  const { run, isPending } = useAdminMutation<{ run: DataSourceRun }, undefined>();
  return { runSource: (id: string) => run(p.runDataSource(id), MTD.POST), isPending };
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
  return useAdminQuery<Paged<AdminUser>>(["users", q, role, page], `${p.users}?${params}`);
};

export const useUpdateUser = () => {
  const { run, isPending } = useAdminMutation<{ user: AdminUser }, { role?: string; is_active?: boolean }>();
  return {
    updateUser: (id: string, body: { role?: string; is_active?: boolean }) => run(p.user(id), MTD.PATCH, body),
    isPending,
  };
};

export const useAuthSummary = () => useAdminQuery<AuthSummary>(["auth", "summary"], p.authSummary);

export const useAuthEvents = (userId?: string) =>
  useAdminQuery<{ events: AuthEvent[] }>(
    ["auth", "events", userId ?? "all"],
    userId ? `${p.authEvents}?user_id=${userId}&limit=50` : `${p.authEvents}?limit=50`,
  );

export const useUserSecurityActions = () => {
  const { run, isPending } = useAdminMutation<{ signedOut?: number; link?: string; expiresInMinutes?: number }, undefined>();
  return {
    revokeSessions: (id: string) => run(p.userRevokeSessions(id), MTD.POST),
    issueResetLink: (id: string) => run(p.userResetLink(id), MTD.POST),
    isPending,
  };
};
