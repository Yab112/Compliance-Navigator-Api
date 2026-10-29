"use client";

import { useFetchData } from "@/hooks/use-query";
import { apiPaths } from "@/lib/constants/api-paths";
import type { APIResponse } from "@/types/global";
import type {
  CatalogInstitution,
  CatalogService,
  CatalogStats,
  DirectoryResult,
  DirectorySource,
  MesobCenter,
} from "@/types/catalog";
import type { Paged } from "@/types/guday";
import type { PublicProvider } from "@/types/provider";
import { withQuery } from "./with-query";

export { withQuery };

export type CatalogSearchParams = {
  q?: string;
  institution_id?: string;
  language?: "en" | "am";
  limit?: number;
  offset?: number;
};

const CATALOG_STALE = 30 * 60 * 1000;

export const useCatalogServices = (params: CatalogSearchParams, enabled = true) =>
  useFetchData<APIResponse<Paged<CatalogService>>>(
    ["catalog", "services", params],
    withQuery(apiPaths.catalog.services, params),
    { enabled, staleTime: CATALOG_STALE },
  );

export const useCatalogService = (id: string) =>
  useFetchData<
    APIResponse<{ service: CatalogService; agents: PublicProvider[]; agentCount: number }>
  >(["catalog", "service", id], apiPaths.catalog.service(id), {
    enabled: !!id,
    staleTime: 60 * 1000,
  });

export const useCatalogInstitutions = () =>
  useFetchData<APIResponse<{ institutions: CatalogInstitution[] }>>(
    ["catalog", "institutions"],
    apiPaths.catalog.institutions,
    { staleTime: CATALOG_STALE },
  );

export const useCatalogCenters = () =>
  useFetchData<APIResponse<{ centers: MesobCenter[] }>>(
    ["catalog", "centers"],
    apiPaths.catalog.centers,
    { staleTime: CATALOG_STALE },
  );

export type GoalServicePayload = {
  goal: string;
  service: CatalogService | null;
  alternatives: CatalogService[];
  agents: PublicProvider[];
  agentCount: number;
  subCityFallback: boolean;
};

/** MESOB service behind a roadmap goal + approved agents for it (sub-city first). */
export const useGoalService = (goal: string, subCity?: string, enabled = true) =>
  useFetchData<APIResponse<GoalServicePayload>>(
    ["catalog", "goal-service", goal, subCity ?? ""],
    withQuery(apiPaths.catalog.goalService(goal), { sub_city: subCity }),
    { enabled: enabled && !!goal, staleTime: 60 * 1000 },
  );

export const useCatalogStats = () =>
  useFetchData<APIResponse<CatalogStats>>(["catalog", "stats"], apiPaths.catalog.stats, {
    staleTime: CATALOG_STALE,
  });

export const useServiceDirectory = (params: {
  q?: string;
  source?: DirectorySource;
  language?: "en" | "am";
  limit?: number;
  offset?: number;
}) =>
  useFetchData<APIResponse<DirectoryResult>>(
    ["catalog", "directory", params],
    withQuery(apiPaths.catalog.directory, params),
    { staleTime: 5 * 60 * 1000 },
  );
