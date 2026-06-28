import {
  DOCUMENT_LABELS,
  PROCESS_GOALS,
} from "@/data/process-graph";
import { getLocationLabel } from "@/constants/addis-locations";
import type { Roadmap, RoadmapRequest, RoadmapStep, StepStatus } from "@/types/roadmap";
import type { ProcessStepTemplate } from "@/data/process-graph";

function resolveStatuses(
  steps: ProcessStepTemplate[],
  held: Set<string>,
): RoadmapStep[] {
  let activeAssigned = false;
  return steps.map((step) => {
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
}

export function buildMockRoadmap(
  goalId: string,
  subCity: string,
  documentsHeld: string[],
  industry?: string,
): Roadmap {
  const goal = PROCESS_GOALS.find((g) => g.id === goalId) ?? PROCESS_GOALS[0];
  const subCityLabel = getLocationLabel(subCity);

  const templates = goal.getSteps(subCity, subCityLabel, {
    fintech: goalId === "fintech_license" || industry === "fintech",
  });

  const held = new Set(documentsHeld);
  const steps = resolveStatuses(templates, held);

  const remaining = steps.filter((s) => s.status !== "completed");
  const totalMin = remaining.reduce(
    (acc, s) => acc + (parseInt(s.estimatedDays, 10) || 5),
    0,
  );

  const request: RoadmapRequest = {
    goal: goalId,
    goalLabel: goal.label,
    category: goal.category,
    subCity,
    subCityLabel,
    industry,
    documentsHeld,
  };

  return {
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    request,
    steps,
    totalEstimatedDays:
      totalMin > 0 ? `~${totalMin}+ business days remaining` : "All steps complete",
    trackedCompleted: [...documentsHeld],
  };
}

export function getDocumentLabel(id: string): string {
  return DOCUMENT_LABELS[id] ?? id;
}
