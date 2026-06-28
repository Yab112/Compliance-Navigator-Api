"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { RoadmapStep } from "@/types/roadmap";
import { cn } from "@/lib/utils";
import { StepDetail } from "./step-detail";

const statusLabel = {
  completed: "Completed",
  active: "Current step",
  blocked: "Upcoming",
} as const;

const statusVariant = {
  completed: "secondary" as const,
  active: "default" as const,
  blocked: "outline" as const,
};

type StepCardProps = {
  step: RoadmapStep;
  onMarkComplete?: (stepId: string) => void;
  canTrack?: boolean;
};

export function StepCard({ step, onMarkComplete, canTrack }: StepCardProps) {
  const [expanded, setExpanded] = useState(step.status === "active");

  return (
    <Card
      className={cn(
        "transition-opacity",
        step.status === "blocked" && "opacity-70",
        step.status === "active" && "ring-primary ring-2",
      )}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-muted-foreground text-xs">Step {step.order}</p>
            <CardTitle className="text-base">{step.title}</CardTitle>
            {step.titleAm && (
              <p className="text-muted-foreground text-xs">{step.titleAm}</p>
            )}
          </div>
          <Badge variant={statusVariant[step.status]}>
            {statusLabel[step.status]}
          </Badge>
        </div>
        <CardDescription>{step.issuingAuthority}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <span>
            <strong>Est. time:</strong> {step.estimatedDays}
          </span>
          <span>
            <strong>Fee:</strong>{" "}
            {step.feeEtb === null
              ? "Confirm at office"
              : step.feeEtb === 0
                ? "Free"
                : `${step.feeEtb} ETB`}
          </span>
          {step.office?.name && (
            <span>
              <strong>Office:</strong> {step.office.name}
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setExpanded((e) => !e)}
          >
            {expanded ? "Hide details" : "Office, fees & checklist"}
          </Button>
          {canTrack && step.status === "active" && onMarkComplete && (
            <Button type="button" size="sm" onClick={() => onMarkComplete(step.id)}>
              Mark as obtained
            </Button>
          )}
        </div>

        {expanded && <StepDetail step={step} />}
      </CardContent>
    </Card>
  );
}
