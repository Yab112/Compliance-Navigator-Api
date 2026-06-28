"use client";

import type { RoadmapStep } from "@/types/roadmap";
import { StepCard } from "./step-card";

type StepTimelineProps = {
  steps: RoadmapStep[];
  onMarkComplete?: (stepId: string) => void;
  canTrack?: boolean;
};

export function StepTimeline({
  steps,
  onMarkComplete,
  canTrack,
}: StepTimelineProps) {
  return (
    <ol className="relative flex flex-col gap-4">
      {steps.map((step, index) => (
        <li key={step.id} className="relative pl-8">
          {index < steps.length - 1 && (
            <span
              className="bg-border absolute top-10 left-3 h-[calc(100%+1rem)] w-px"
              aria-hidden
            />
          )}
          <span
            className={`absolute left-0 flex size-6 items-center justify-center text-xs font-medium ${
              step.status === "completed"
                ? "bg-primary text-primary-foreground"
                : step.status === "active"
                  ? "bg-primary/20 text-primary ring-primary ring-2"
                  : "bg-muted text-muted-foreground"
            }`}
          >
            {step.order}
          </span>
          <StepCard
            step={step}
            onMarkComplete={onMarkComplete}
            canTrack={canTrack}
          />
        </li>
      ))}
    </ol>
  );
}
