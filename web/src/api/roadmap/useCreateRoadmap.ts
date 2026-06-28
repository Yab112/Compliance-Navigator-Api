"use client";

import { AxiosError } from "axios";
import useMutationFunc from "@/hooks/use-mutation";
import { MTD } from "@/lib/constants/methods";
import { apiPaths } from "@/lib/constants/api-paths";
import { buildMockRoadmap } from "@/lib/mock-roadmap";
import type { APIResponse } from "@/types/global";
import type { Roadmap } from "@/types/roadmap";
import type { RoadmapRequestInput } from "@/schemas/roadmap";

export class RoadmapApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "RoadmapApiError";
  }
}

export const useCreateRoadmap = () => {
  const { mutateAsync, isPending } = useMutationFunc<
    APIResponse<{ roadmap: Roadmap }>,
    RoadmapRequestInput
  >();

  const createRoadmap = async (input: RoadmapRequestInput): Promise<Roadmap> => {
    try {
      const data = await mutateAsync({
        url: apiPaths.roadmaps,
        method: MTD.POST,
        body: input,
        headers: { "Content-Type": "application/json" },
      });
      return data.payload.roadmap;
    } catch (err) {
      if (err instanceof AxiosError) {
        if (err.code === "ERR_NETWORK" || !err.response) {
          return buildMockRoadmap(
            input.goal,
            input.subCity,
            input.documentsHeld,
            input.industry,
          );
        }
        const msg =
          (err.response?.data as { detail?: string })?.detail ||
          (err.response?.data as { message?: string })?.message ||
          "Could not create roadmap";
        throw new RoadmapApiError(msg, err.response?.status);
      }
      throw err;
    }
  };

  return {
    createRoadmap,
    isCreating: isPending,
  };
};
