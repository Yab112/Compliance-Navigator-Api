"use client";

import { useQueryClient } from "@tanstack/react-query";
import useAxiosAuth from "@/hooks/use-axios-auth";
import useMutationFunc from "@/hooks/use-mutation";
import { useFetchData } from "@/hooks/use-query";
import { withQuery } from "@/api/catalog/with-query";
import { apiPaths } from "@/lib/constants/api-paths";
import { MTD } from "@/lib/constants/methods";
import type { APIResponse } from "@/types/global";
import type { Paged } from "@/types/guday";
import type {
  AdminProvider,
  AdminReview,
  ClientRecord,
  Hire,
  HireInput,
  HireStatus,
  LicenseStatus,
  MarketplaceStats,
  MyProvider,
  ProviderJoinInput,
  ProviderListParams,
  ProviderProfileView,
  ProviderStatus,
  ProviderType,
  PublicProvider,
  Review,
  ReviewChange,
} from "@/types/provider";

const p = apiPaths.providers;

// ---------------------------------------------------------------- public

export const useProviders = (params: ProviderListParams, enabled = true) =>
  useFetchData<APIResponse<Paged<PublicProvider> & { countsByType: Partial<Record<ProviderType, number>> }>>(
    ["providers", "list", params],
    withQuery(p.list, params),
    { enabled, staleTime: 60 * 1000 },
  );

export const useProvider = (slug: string) =>
  useFetchData<APIResponse<{ provider: ProviderProfileView }>>(["providers", "profile", slug], p.profile(slug), {
    enabled: !!slug,
    staleTime: 30 * 1000,
    retry: false,
  });

export type ReviewSort = "recent" | "highest" | "lowest";

export const useProviderReviews = (slug: string, offset: number, enabled: boolean, sort: ReviewSort = "recent") =>
  useFetchData<APIResponse<Paged<Review>>>(
    ["providers", "reviews", slug, offset, sort],
    withQuery(p.reviews(slug), { limit: 10, offset, sort }),
    { enabled, staleTime: 30 * 1000 },
  );

// ---------------------------------------------------------------- my provider profile

export const useMyProvider = (enabled = true) =>
  useFetchData<APIResponse<{ provider: MyProvider | null }>>(["providers", "me"], p.me, {
    enabled,
    staleTime: 0,
    refetchOnMount: true,
  });

export type JobGroup = "new" | "in_progress" | "completed" | "declined";
export type JobCounts = Record<JobGroup, number>;
export const JOBS_PAGE_SIZE = 20;

/** One page of the provider's jobs in a group, plus the count of every group. */
export const useMyJobs = (group: JobGroup, page = 0, enabled = true) =>
  useFetchData<APIResponse<Paged<Hire> & { counts: JobCounts }>>(
    ["providers", "me", "jobs", group, page],
    withQuery(p.myJobs, { group, limit: JOBS_PAGE_SIZE, offset: page * JOBS_PAGE_SIZE }),
    {
      enabled,
      staleTime: 0,
      refetchInterval: 30 * 1000, // the job cards and group counts stay current
    },
  );

export const MY_REVIEWS_PAGE_SIZE = 10;

export const useMyProviderReviews = (page = 0, enabled = true) =>
  useFetchData<APIResponse<Paged<Review>>>(
    ["providers", "me", "reviews", page],
    withQuery(p.myReviews, { limit: MY_REVIEWS_PAGE_SIZE, offset: page * MY_REVIEWS_PAGE_SIZE }),
    { enabled, staleTime: 0 },
  );

/** Join as a provider: multipart (JSON `data` + optional photo, licence copy, ID copy). */
export const useJoinMarketplace = () => {
  const axiosAuth = useAxiosAuth();
  const queryClient = useQueryClient();
  return async (
    input: ProviderJoinInput,
    files: { photo?: File | null; licenseDocument?: File | null; idDocument?: File | null },
  ) => {
    const form = new FormData();
    form.append("data", JSON.stringify(input));
    if (files.photo) form.append("photo", files.photo);
    if (files.licenseDocument) form.append("license_document", files.licenseDocument);
    if (files.idDocument) form.append("id_document", files.idDocument);
    const res = await axiosAuth.post<APIResponse<{ provider: MyProvider }>>(`/${p.join}`, form);
    await queryClient.invalidateQueries({ queryKey: ["providers"] });
    return res.data.payload.provider;
  };
};

export const useUploadProviderFile = () => {
  const axiosAuth = useAxiosAuth();
  const queryClient = useQueryClient();
  return async (kind: "photo" | "license", file: File) => {
    const form = new FormData();
    form.append(kind === "photo" ? "photo" : "document", file);
    await axiosAuth.post(`/${kind === "photo" ? p.mePhoto : p.meLicense}`, form);
    await queryClient.invalidateQueries({ queryKey: ["providers"] });
  };
};

export const useRemoveProviderPhoto = () => {
  const axiosAuth = useAxiosAuth();
  const queryClient = useQueryClient();
  return async () => {
    await axiosAuth.delete(`/${p.mePhoto}`);
    await queryClient.invalidateQueries({ queryKey: ["providers"] });
  };
};

// ---------------------------------------------------------------- hires (client)

export type HireScope = "active" | "history";
export const HIRES_PAGE_SIZE = 20;

/** One page of the client's hires in a tab, plus the count of both tabs. */
export const useMyHires = (scope: HireScope, page = 0, enabled = true) =>
  useFetchData<APIResponse<Paged<Hire> & { counts: Record<HireScope, number> }>>(
    ["hires", "mine", scope, page],
    withQuery(apiPaths.hires.list, { scope, limit: HIRES_PAGE_SIZE, offset: page * HIRES_PAGE_SIZE }),
    {
      enabled,
      staleTime: 0,
      refetchOnMount: true,
      refetchInterval: 30 * 1000, // the hire cards stay current
    },
  );

/** Hires and jobs that wait on the signed-in user: header badges */
export const useAttention = (enabled = true) =>
  useFetchData<APIResponse<{ hires: number; jobs: number }>>(["hires", "attention"], apiPaths.attention, {
    enabled,
    staleTime: 0,
    refetchInterval: 30 * 1000,
  });

/** Your record as a client, as providers see it */
export const useMyClientRecord = (enabled = true) =>
  useFetchData<APIResponse<{ record: ClientRecord }>>(["hires", "record"], apiPaths.hires.myRecord, { enabled, staleTime: 0 });

/** JSON action that refreshes marketplace queries (public, mine and admin) on success. */
export const useMarketAction = <TBody = unknown, TResult = unknown>() => {
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<TResult>, TBody>();
  const run = async (url: string, method: MTD, body?: TBody) => {
    const data = await mutateAsync({ url, method, body });
    await Promise.all(
      [["providers"], ["hires"], ["admin", "market"], ["catalog", "service"], ["catalog", "goal-service"]].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    );
    return data.payload;
  };
  return { run, isPending };
};

export const useCreateHire = () => {
  const { run, isPending } = useMarketAction<HireInput, { hire: Hire }>();
  return { createHire: (body: HireInput) => run(apiPaths.hires.list, MTD.POST, body), isCreating: isPending };
};

// ---------------------------------------------------------------- admin

export type AdminProviderParams = {
  type?: ProviderType;
  status?: ProviderStatus;
  license_status?: LicenseStatus;
  q?: string;
  limit?: number;
  offset?: number;
};

export const useAdminProviders = (params: AdminProviderParams) =>
  useFetchData<APIResponse<Paged<AdminProvider>>>(
    ["admin", "market", "providers", params],
    withQuery(apiPaths.admin.marketProviders, params),
    { staleTime: 0 },
  );

export const useAdminProvider = (id: string) =>
  useFetchData<APIResponse<{ provider: AdminProvider }>>(["admin", "market", "provider", id], apiPaths.admin.marketProvider(id), {
    enabled: !!id,
    staleTime: 0,
  });

export const useMarketStats = () =>
  useFetchData<APIResponse<MarketplaceStats>>(["admin", "market", "stats"], apiPaths.admin.marketStats, { staleTime: 0 });

export type AdminHireParams = {
  status?: HireStatus;
  disputed?: boolean;
  /** Accepted but not paid for 48 hours: staff call both sides */
  follow_up?: boolean;
  provider_id?: string;
  q?: string;
  limit?: number;
  offset?: number;
};

export const useAdminHires = (params: AdminHireParams) =>
  useFetchData<APIResponse<Paged<Hire>>>(["admin", "market", "hires", params], withQuery(apiPaths.admin.marketHires, params), {
    staleTime: 0,
  });

export const ADMIN_MARKET_PAGE_SIZE = 25;

export const useAdminReviews = (params: { hidden?: boolean; max_rating?: number; offset?: number }, enabled = true) =>
  useFetchData<APIResponse<Paged<AdminReview>>>(
    ["admin", "market", "reviews", params],
    withQuery(apiPaths.admin.marketReviews, { ...params, limit: ADMIN_MARKET_PAGE_SIZE }),
    { enabled, staleTime: 0 },
  );

export type ReviewChangeStatus = ReviewChange["status"];

export const useAdminReviewChanges = (status: ReviewChangeStatus, page = 0, enabled = true) =>
  useFetchData<APIResponse<Paged<ReviewChange> & { pending: number }>>(
    ["admin", "market", "review-changes", status, page],
    withQuery(apiPaths.admin.reviewChanges, { status, limit: ADMIN_MARKET_PAGE_SIZE, offset: page * ADMIN_MARKET_PAGE_SIZE }),
    { enabled, staleTime: 0 },
  );
