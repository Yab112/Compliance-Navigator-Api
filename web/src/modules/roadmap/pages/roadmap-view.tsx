"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@cn/ui/button";
import { Badge } from "@cn/ui/badge";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@cn/ui/card";
import { StepTimeline } from "@/components/roadmap/step-timeline";
import { RoadmapEmptyState } from "@/modules/roadmap/components/roadmap-empty-state";
import { PathComplete } from "@/modules/roadmap/components/path-complete";
import { RoadmapChatPanel } from "@/modules/roadmap/components/roadmap-chat-panel";
import { useQueryClient } from "@tanstack/react-query";
import { syncStep, useRoadmapSaved, useSavePath } from "@/api/roadmap/saved";
import { useRoadmapStore } from "@/store/roadmap-store";
import { useUserStore } from "@/store";
import { PageNav } from "@cn/ui/layout/page-nav";

const CATEGORY_LABELS: Record<string, string> = {
  business: "Business · ንግድ",
  personal: "Personal · የግል",
};

export function RoadmapView() {
  const router = useRouter();
  const roadmap = useRoadmapStore((s) => s.current);
  const setCurrent = useRoadmapStore((s) => s.setCurrent);
  const markStepComplete = useRoadmapStore((s) => s.markStepComplete);
  const saveCurrent = useRoadmapStore((s) => s.saveCurrent);
  const user = useUserStore((s) => s.user);
  const queryClient = useQueryClient();
  const savePath = useSavePath();
  // From GET /roadmaps/{id}: also covers the path opened from /roadmap, which may never have been fetched
  const isSaved = useRoadmapSaved(roadmap?.id ?? null);

  const save = () => {
    if (!roadmap) return;
    saveCurrent();
    savePath.mutate(roadmap.id);
  };
  const markObtained = (stepId: string) => {
    markStepComplete(stepId);
    // Signed in: progress is kept with the path on the server, not only in this browser
    if (user && roadmap) {
      void syncStep(roadmap.id, stepId, true)
        .then(() => queryClient.invalidateQueries({ queryKey: ["roadmaps", "mine"] }))
        .catch(() => undefined);
    }
  };

  useEffect(() => {
    if (roadmap?.steps.some((s) => !s.office?.name)) {
      setCurrent(roadmap);
    }
  }, [roadmap, setCurrent]);

  if (!roadmap) {
    return (
      <div className="mx-auto max-w-lg px-4 py-10">
        <PageNav label="My current path" className="mb-8" />
        <RoadmapEmptyState />
      </div>
    );
  }

  const completed = roadmap.steps.filter((s) => s.status === "completed").length;
  const active = roadmap.steps.find((s) => s.status === "active");
  const nextStepLabel = active
    ? (active.office?.name ?? active.issuingAuthority ?? active.title)
    : "All requirements met";

  return (
    <div className="flex h-[calc(100dvh-var(--nav-h))] overflow-hidden">
      {/* Left, scrollable roadmap content */}
      <div className="flex-1 overflow-y-auto px-4 py-10 lg:px-8">
        <div className="mx-auto max-w-2xl">
          <PageNav label={`Path to ${roadmap.request.goalLabel}`} />
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <Badge variant="secondary" className="mb-2">
                {CATEGORY_LABELS[roadmap.request.category] ?? roadmap.request.category}
              </Badge>
              <h1 className="text-2xl font-semibold tracking-tight">
                Path to: {roadmap.request.goalLabel}
              </h1>
              <p className="text-muted-foreground mt-2 text-sm">
                {roadmap.request.subCityLabel} · {completed} of {roadmap.steps.length}{" "}
                steps complete
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => router.push("/roadmap/new")}>
                Change goal
              </Button>
              {user ? (
                isSaved ? (
                  <Link href="/account/paths">
                    <Button variant="secondary">Saved ✓ · view all</Button>
                  </Link>
                ) : (
                  <Button onClick={save} disabled={savePath.isPending}>
                    {savePath.isPending ? "Saving…" : "Save path"}
                  </Button>
                )
              ) : (
                <Link href="/login">
                  <Button variant="secondary">Sign in to save</Button>
                </Link>
              )}
            </div>
          </div>

          {roadmap.steps.length > 0 && completed === roadmap.steps.length && <PathComplete roadmap={roadmap} />}

          <div className="mb-8 grid gap-4 sm:grid-cols-3">
            <Card size="sm">
              <CardHeader>
                <CardTitle>Progress</CardTitle>
                <CardDescription>
                  {completed} completed · track each step as you obtain documents
                </CardDescription>
              </CardHeader>
            </Card>
            <Card size="sm">
              <CardHeader>
                <CardTitle>Timeline</CardTitle>
                <CardDescription>{roadmap.totalEstimatedDays}</CardDescription>
              </CardHeader>
            </Card>
            <Card size="sm">
              <CardHeader>
                <CardTitle>Go here next</CardTitle>
                <CardDescription>{nextStepLabel}</CardDescription>
              </CardHeader>
            </Card>
          </div>

          <p className="text-muted-foreground mb-6 text-xs leading-relaxed">
            Each step shows the exact office, address, phone, working hours, fee,
            payment methods, documents to prepare, and common rejection reasons.
            Expand a step for full detail and map link.
          </p>

          <StepTimeline
            steps={roadmap.steps}
            onMarkComplete={markObtained}
            canTrack
          />
        </div>
      </div>

      {/* Right, sticky chat panel (desktop only) */}
      <div className="hidden w-80 shrink-0 lg:flex lg:w-96 lg:flex-col">
        <RoadmapChatPanel roadmap={roadmap} />
      </div>
    </div>
  );
}
