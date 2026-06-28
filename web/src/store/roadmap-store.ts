import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Roadmap, RoadmapStep, StepStatus } from "@/types/roadmap";
import { normalizeRoadmap } from "@/lib/normalize-roadmap";

type RoadmapStore = {
  current: Roadmap | null;
  saved: Roadmap[];
  setCurrent: (roadmap: Roadmap | null) => void;
  markStepComplete: (stepId: string) => void;
  saveCurrent: () => void;
  clearSaved: () => void;
};

function recomputeStepStatuses(roadmap: Roadmap): Roadmap {
  const held = new Set(roadmap.trackedCompleted);
  let activeAssigned = false;
  const steps: RoadmapStep[] = roadmap.steps.map((step) => {
    let status: StepStatus;
    if (held.has(step.id)) {
      status = "completed";
    } else if (!activeAssigned) {
      status = "active";
      activeAssigned = true;
    } else {
      status = "blocked";
    }
    return { ...step, status };
  });
  return { ...roadmap, steps };
}

export const useRoadmapStore = create<RoadmapStore>()(
  persist(
    (set, get) => ({
      current: null,
      saved: [],
      setCurrent: (roadmap) =>
        set({ current: roadmap ? normalizeRoadmap(roadmap) : null }),
      markStepComplete: (stepId) => {
        const { current } = get();
        if (!current) return;
        const normalized = normalizeRoadmap(current);
        if (!normalized) return;
        const tracked = normalized.trackedCompleted.includes(stepId)
          ? normalized.trackedCompleted
          : [...normalized.trackedCompleted, stepId];
        set({
          current: recomputeStepStatuses({
            ...normalized,
            trackedCompleted: tracked,
          }),
        });
      },
      saveCurrent: () => {
        const { current, saved } = get();
        if (!current) return;
        const normalized = normalizeRoadmap(current);
        if (!normalized) return;
        const exists = saved.some((r) => r.id === normalized.id);
        set({
          saved: exists ? saved : [normalized, ...saved].slice(0, 10),
        });
      },
      clearSaved: () => set({ saved: [] }),
    }),
    {
      name: "compliance-roadmaps",
      version: 2,
      migrate: (persisted) => {
        const state = persisted as RoadmapStore;
        return {
          ...state,
          current: normalizeRoadmap(state.current),
          saved: (state.saved ?? [])
            .map((r) => normalizeRoadmap(r))
            .filter((r): r is Roadmap => r !== null),
        };
      },
    },
  ),
);
