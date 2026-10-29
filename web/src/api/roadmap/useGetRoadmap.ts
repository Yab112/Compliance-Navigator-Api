"use client";

import { useFetchData } from "@cn/core/hooks/use-query";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import type { APIResponse } from "@cn/core/types/global";
import type { Roadmap } from "@/types/roadmap";

export const useGetRoadmap = (id: string | null, enabled = true) => {
  const queryKey = ["roadmaps", id] as const;
  const url = id ? `${apiPaths.roadmaps}/${id}` : apiPaths.roadmaps;

  const { data, isLoading, isError, refetch } = useFetchData<
    APIResponse<{ roadmap: Roadmap; saved?: boolean }>
  >(queryKey, url, {
    enabled: enabled && !!id,
    retry: false,
  });

  return {
    roadmap: data?.payload?.roadmap ?? null,
    isLoading,
    isError,
    refetchRoadmap: refetch,
  };
};
