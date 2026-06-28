"use client";

import { useFetchData } from "@/hooks/use-query";
import { apiPaths } from "@/lib/constants/api-paths";
import { PROCESS_GOALS } from "@/data/process-graph";
import type { APIResponse } from "@/types/global";

export interface ProcessGoalSummary {
  id: string;
  label: string;
  description: string;
}

const queryKey = ["processes"] as const;

export const useGetProcesses = (enabled = true) => {
  const { data, isLoading, isError, refetch } = useFetchData<
    APIResponse<{ processes: ProcessGoalSummary[] }>
  >(queryKey, apiPaths.processes, {
    enabled,
    retry: false,
    staleTime: 10 * 60 * 1000,
  });

  const fallback: ProcessGoalSummary[] = PROCESS_GOALS.map((g) => ({
    id: g.id,
    label: g.label,
    description: g.description,
  }));

  return {
    processes: isError ? fallback : (data?.payload?.processes ?? fallback),
    isLoading,
    isError,
    refetchProcesses: refetch,
  };
};
