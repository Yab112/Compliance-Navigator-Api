"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAdminMutation, useAdminQuery } from "../admin";
import { withQuery } from "../catalog/with-query";
import { useFetchData } from "../../hooks/use-query";
import { api } from "../../lib/api";
import { apiPaths } from "../../lib/constants/api-paths";
import { MTD } from "../../lib/constants/methods";
import type { APIResponse } from "../../types/global";
type Paged<T> = { total: number; items: T[] };
import type {
  AdminOrganization,
  Branch,
  BranchInput,
  EligibilityResult,
  ImportReport,
  MemberOrganization,
  OrgInvite,
  OrgReport,
  OrgAnalytics,
  OrgServiceListItem,
  PublicOrganization,
  PublicOrganizationDetail,
  PublicService,
  RequirementOptions,
  ServiceInput,
  ServicePath,
  Submission,
  SubmissionDetail,
  WorkingService,
} from "../../types/organizations";

const p = apiPaths.organizations;
const o = apiPaths.org;
const a = apiPaths.admin;

// ---------------------------------------------------------------- public

export type OrgDirectoryParams = { q?: string; type?: string; region?: string; limit?: number; offset?: number };

export const useOrganizations = (params: OrgDirectoryParams) =>
  useFetchData<APIResponse<Paged<PublicOrganization>>>(["orgs", "directory", params], withQuery(p.directory, params), {
    staleTime: 60 * 1000,
  });

export const useOrganization = (slug: string) =>
  useFetchData<APIResponse<{ organization: PublicOrganizationDetail }>>(["orgs", "profile", slug], p.profile(slug), {
    enabled: !!slug,
    staleTime: 60 * 1000,
  });

export const usePublicService = (slug: string, serviceSlug: string) =>
  useFetchData<APIResponse<{ service: PublicService }>>(
    ["orgs", "service", slug, serviceSlug],
    p.service(slug, serviceSlug),
    { enabled: !!slug && !!serviceSlug, staleTime: 60 * 1000 },
  );

export const useServicePath = (serviceId: string | undefined) =>
  useFetchData<APIResponse<ServicePath>>(["orgs", "path", serviceId], p.path(serviceId ?? ""), {
    enabled: !!serviceId,
    staleTime: 60 * 1000,
  });

export const useEligibility = (serviceId: string) =>
  useMutation({
    mutationFn: async (answers: Record<string, string | number | boolean | null>) => {
      const res = await api.post<APIResponse<EligibilityResult>>(`/${p.eligibility(serviceId)}`, { answers });
      return res.data.payload;
    },
  });

// ---------------------------------------------------------------- organization workspace

export const useMyOrganizations = (enabled = true) =>
  useFetchData<APIResponse<{ organizations: MemberOrganization[]; invites: OrgInvite[] }>>(["orgs", "mine"], p.mine, {
    enabled,
    staleTime: 0,
    refetchOnMount: true,
  });

export const useWorkspace = (orgId: string, enabled = true) =>
  useFetchData<APIResponse<{ organization: MemberOrganization; services: OrgServiceListItem[] }>>(
    ["orgs", "workspace", orgId],
    o.workspace(orgId),
    { enabled: enabled && !!orgId, staleTime: 0, refetchOnMount: true },
  );

export const useWorkingService = (orgId: string, serviceId: string | null) =>
  useFetchData<APIResponse<{ service: WorkingService }>>(
    ["orgs", "working", orgId, serviceId],
    o.service(orgId, serviceId ?? ""),
    { enabled: !!orgId && !!serviceId, staleTime: 0, refetchOnMount: true },
  );

export const useOrgAnalytics = (orgId: string) =>
  useFetchData<APIResponse<OrgAnalytics>>(["orgs", "analytics", orgId], o.analytics(orgId), {
    enabled: !!orgId,
    staleTime: 0,
  });

export const useRegistrationCheck = (orgId: string, enabled = true) =>
  useFetchData<APIResponse<{ problems: string[]; services: OrgServiceListItem[] }>>(
    ["orgs", "registration-check", orgId],
    o.registrationCheck(orgId),
    { enabled: enabled && !!orgId, staleTime: 0, refetchOnMount: true },
  );

export const useOrgReports = (orgId: string, enabled = true) =>
  useFetchData<APIResponse<{ reports: OrgReport[] }>>(["orgs", "reports", orgId], o.reports(orgId), {
    enabled: enabled && !!orgId,
    staleTime: 0,
    refetchOnMount: true,
  });

/** Check a CSV of services; with dryRun false, the valid rows become drafts. */
export const useImportServices = (orgId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, dryRun }: { file: File; dryRun: boolean }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("dry_run", String(dryRun));
      const res = await api.post<APIResponse<ImportReport>>(`/${o.importServices(orgId)}`, form);
      return res.data.payload;
    },
    onSuccess: (report) => {
      if (!report.dry_run) void queryClient.invalidateQueries({ queryKey: ["orgs"] });
    },
  });
};

export const useRequirementOptions = (q: string, enabled = true) =>
  useFetchData<APIResponse<RequirementOptions>>(["orgs", "req-options", q], withQuery(p.requirementOptions, { q }), {
    enabled,
    staleTime: 30 * 1000,
  });

/** Any JSON call in the organization workspace; refreshes workspace data afterwards. */
export const useOrgAction = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ url, method, body }: { url: string; method: string; body?: unknown }) => {
      const res = await api.request<APIResponse<Record<string, unknown>>>({ url: `/${url}`, method, data: body });
      return res.data.payload;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["orgs"] }),
  });
};

export const useSaveService = (orgId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ serviceId, body }: { serviceId: string | null; body: ServiceInput }) => {
      const res = serviceId
        ? await api.put<APIResponse<{ service: WorkingService }>>(`/${o.service(orgId, serviceId)}`, body)
        : await api.post<APIResponse<{ service: WorkingService }>>(`/${o.services(orgId)}`, body);
      return res.data.payload.service;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["orgs"] }),
  });
};

export type OrgRegistrationInput = {
  draft?: boolean;
  name: string;
  name_am?: string;
  org_type: string;
  sector?: string;
  description?: string;
  website?: string;
  phone?: string;
  email?: string;
  hq_address?: string;
  region?: string;
  sub_city?: string;
  representative_name?: string;
  representative_title?: string;
  official_email?: string;
  branches: BranchInput[];
};

export const useRegisterOrganization = () => {
  const queryClient = useQueryClient();
  return async (input: OrgRegistrationInput, letter: File | null, logo: File | null) => {
    const form = new FormData();
    form.append("data", JSON.stringify(input));
    if (letter) form.append("authorization_letter", letter);
    if (logo) form.append("logo", logo);
    const res = await api.post<APIResponse<{ organization: MemberOrganization }>>(`/${p.register}`, form);
    await queryClient.invalidateQueries({ queryKey: ["orgs"] });
    return res.data.payload.organization;
  };
};

/** Logo, authorization letter or a PDF form; returns the API payload. */
export const useOrgUpload = () => {
  const queryClient = useQueryClient();
  return async <T>(url: string, field: string, file: File) => {
    const form = new FormData();
    form.append(field, file);
    const res = await api.post<APIResponse<T>>(`/${url}`, form);
    await queryClient.invalidateQueries({ queryKey: ["orgs"] });
    return res.data.payload;
  };
};

export type { Branch };

// ---------------------------------------------------------------- staff review

export const ADMIN_ORGS_PAGE_SIZE = 25;

export const useAdminOrganizations = (status: string, q: string, page = 0, size = ADMIN_ORGS_PAGE_SIZE) =>
  useAdminQuery<Paged<AdminOrganization> & { confirm_every_days: number }>(
    ["organizations", status, q, page, size],
    withQuery(a.organizations, { status, q, limit: size, offset: page * size }),
  );

/** Download the organizations list (same filters) as a CSV file. */
export const downloadOrganizationsCsv = async (status: string, q: string) => {
  const res = await api.get(`/${a.organizationsExport}`, { params: { status, q: q || undefined }, responseType: "blob" });
  const url = URL.createObjectURL(new Blob([res.data as BlobPart], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `organizations-${status}-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

export const useAdminOrganization = (id: string) =>
  useAdminQuery<{ organization: AdminOrganization }>(["organization", id], a.organization(id), { enabled: !!id });

type OrgReviewBody = { action: string; note?: string; catalog_institution_id?: string };

export const useReviewOrganization = () => {
  const { run, isPending } = useAdminMutation<{ organization: AdminOrganization }, OrgReviewBody>();
  return {
    review: (id: string, body: OrgReviewBody) => run(a.organizationReview(id), MTD.POST, body),
    isPending,
  };
};

export const useSubmissions = (status: string, page = 0, q = "", size = ADMIN_ORGS_PAGE_SIZE) =>
  useAdminQuery<{ submissions: Submission[]; total: number }>(
    ["submissions", status, q, page, size],
    withQuery(a.submissions, { status, q, limit: size, offset: page * size }),
  );

export const useSubmission = (id: string) =>
  useAdminQuery<{ submission: SubmissionDetail }>(["submission", id], a.submission(id), { enabled: !!id });

export const useReviewSubmission = () => {
  const { run, isPending } = useAdminMutation<{ submission: SubmissionDetail }, { action: string; note?: string }>();
  return {
    review: (id: string, body: { action: string; note?: string }) => run(a.submissionReview(id), MTD.POST, body),
    isPending,
  };
};

export const useOrganizationsFreshness = () =>
  useAdminQuery<{ services: { id: string; name: string; last_confirmed_at: string | null; org_id: string; org_name: string }[] }>(
    ["organizations-freshness"],
    a.organizationsFreshness,
  );
