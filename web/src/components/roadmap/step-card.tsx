"use client";

import { useState } from "react";
import { Badge } from "@cn/ui/badge";
import { Button } from "@cn/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@cn/ui/card";
import type { RoadmapStep } from "@/types/roadmap";
import { cn } from "@cn/core/lib/utils";
import { StepDetail } from "@/components/roadmap/step-detail";

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

/** Paths store a bare range like "5–8"; say what it counts. */
function withDays(value: string): string {
  if (!/^[~\d\s–-]+$/.test(value)) return value;
  return `${value} ${value.trim() === "1" ? "day" : "days"}`;
}

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
            <strong>Est. time:</strong> {withDays(step.estimatedDays)}
          </span>
          <span>
            <strong>Fee:</strong>{" "}
            {step.feeEtb === null
              ? "Confirm at office"
              : step.feeEtb === 0
                ? "Free"
                : `${step.feeEtb} ETB`}
          </span>
          {step.orgService ? (
            <Badge variant="outline" className="h-auto py-0">
              {step.orgService.branch?.window ? `${step.orgService.branch.name} · ${step.orgService.branch.window}` : step.orgService.orgName}
              {step.orgService.confirmedDaysAgo != null && !step.orgService.confirmationDue && " · confirmed"}
            </Badge>
          ) : step.office?.name && (
            <span>
              <strong>Office:</strong> {step.office.name}
            </span>
          )}
          {step.mesob && (
            <Badge variant="outline" className="h-auto py-0">
              At MESOB · {step.mesob.institution}
            </Badge>
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
