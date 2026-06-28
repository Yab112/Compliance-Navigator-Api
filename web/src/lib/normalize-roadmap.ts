import type { Roadmap } from "@/types/roadmap";
import { buildMockRoadmap } from "@/lib/mock-roadmap";
import { PROCESS_GOALS } from "@/data/process-graph";

type LegacyRequest = Roadmap["request"] & {
  target?: string;
  entityType?: string;
};

/** Map persisted / legacy roadmaps to the current graph schema (office, fees, etc.). */
export function normalizeRoadmap(roadmap: Roadmap | null): Roadmap | null {
  if (!roadmap) return null;

  const req = roadmap.request as LegacyRequest;
  const goal =
    req.goal ??
    req.target ??
    (req.industry === "fintech" ? "fintech_license" : "trade_license");

  const subCity = req.subCity ?? "bole";
  const tracked =
    roadmap.trackedCompleted ??
    req.documentsHeld ??
    [];

  const needsRebuild = roadmap.steps.some(
    (s) =>
      !s.office?.name ||
      !Array.isArray(s.paymentMethods) ||
      !Array.isArray(s.requiredInputs),
  );

  if (!needsRebuild && req.goalLabel && req.subCityLabel) {
    return roadmap;
  }

  const rebuilt = buildMockRoadmap(goal, subCity, tracked, req.industry);

  return {
    ...rebuilt,
    id: roadmap.id,
    createdAt: roadmap.createdAt,
    request: {
      ...rebuilt.request,
      goal: PROCESS_GOALS.find((g) => g.id === goal)?.id ?? rebuilt.request.goal,
      goalLabel:
        req.goalLabel ??
        PROCESS_GOALS.find((g) => g.id === goal)?.label ??
        rebuilt.request.goalLabel,
    },
    trackedCompleted: tracked,
  };
}
