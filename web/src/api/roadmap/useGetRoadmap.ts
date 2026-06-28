"use client";

import { useFetchData } from "@/hooks/use-query";
import { apiPaths } from "@/lib/constants/api-paths";
import type { APIResponse } from "@/types/global";
import type { Roadmap } from "@/types/roadmap";

export const useGetRoadmap = (id: string | null, enabled = true) => {
  const queryKey = ["roadmaps", id] as const;
  const url = id ? `${apiPaths.roadmaps}/${id}` : apiPaths.roadmaps;

  const { data, isLoading, isError, refetch } = useFetchData<
    APIResponse<{ roadmap: Roadmap }>
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
