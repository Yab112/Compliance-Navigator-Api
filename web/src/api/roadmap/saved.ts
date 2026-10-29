"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { withQuery } from "@cn/core/api/catalog/with-query";
import { api } from "@cn/core/lib/api";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { useUserStore } from "@cn/core/store/user-store";
import type { APIResponse } from "@cn/core/types/global";
import type { Roadmap } from "@/types/roadmap";

export type SavedPath = {
  id: string;
  goal: string;
  goalLabel: string;
  subCity: string | null;
  subCityLabel: string | null;
  category?: string | null;
  steps: number;
  completed: number;
  createdAt: string;
  updatedAt: string;
};

const KEY = ["roadmaps", "mine"] as const;
export const SAVED_PATHS_PAGE_SIZE = 20;

/** One page of the paths saved to the signed-in account (kept on the server, so they follow you between devices). */
export const useSavedPaths = (page = 0) => {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  return useQuery({
    queryKey: [...KEY, page],
    enabled: signedIn,
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (
        await api.get<APIResponse<{ items: SavedPath[]; total: number }>>(
          withQuery(apiPaths.roadmaps, { limit: SAVED_PATHS_PAGE_SIZE, offset: page * SAVED_PATHS_PAGE_SIZE }),
        )
      ).data.payload,
  });
};

type RoadmapResponse = APIResponse<{ roadmap: Roadmap; saved?: boolean }>;

/** Whether this roadmap is saved to the signed-in account, from GET /roadmaps/{id} (shares its cache with useGetRoadmap). */
export const useRoadmapSaved = (id: string | null) => {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  const { data } = useQuery({
    queryKey: ["roadmaps", id],
    enabled: signedIn && !!id,
    retry: false,
    staleTime: 5 * 60 * 1000,
    queryFn: async () => (await api.get<RoadmapResponse>(`${apiPaths.roadmaps}/${id}`)).data,
  });
  return !!data?.payload?.saved;
};

/** Flip the saved flag in the cached roadmap without refetching it (a refetch would reload its steps). */
const setSavedFlag = (qc: ReturnType<typeof useQueryClient>, id: string, saved: boolean) =>
  qc.setQueryData<RoadmapResponse>(["roadmaps", id], (old) => (old ? { ...old, payload: { ...old.payload, saved } } : old));

export const useSavePath = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`${apiPaths.roadmaps}/${id}/save`),
    onSuccess: (_, id) => {
      setSavedFlag(qc, id, true);
      return qc.invalidateQueries({ queryKey: KEY });
    },
  });
};

export const useRemovePath = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`${apiPaths.roadmaps}/${id}`),
    onSuccess: (_, id) => {
      setSavedFlag(qc, id, false);
      return qc.invalidateQueries({ queryKey: KEY });
    },
  });
};

/** Record a step as obtained on the server too, so progress isn't only in this browser. */
export const syncStep = (roadmapId: string, stepId: string, completed: boolean) =>
  api.patch(`${apiPaths.roadmaps}/${roadmapId}/steps/${stepId}`, { completed });
