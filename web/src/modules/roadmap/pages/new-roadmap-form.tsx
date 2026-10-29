"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { GoalPicker } from "@/components/roadmap/goal-picker";
import { SubCityPicker } from "@/components/roadmap/sub-city-picker";
import {
  ALL_DOCUMENT_IDS,
  DOCUMENT_LABELS,
  PROCESS_GOALS,
} from "@/constants/compliance";
import { getLocationLabel } from "@/constants/addis-locations";
import { RoadmapApiError, useCreateRoadmap } from "@/api/roadmap";
import { roadmapRequestSchema } from "@/schemas/roadmap";
import { useRoadmapStore } from "@/store/roadmap-store";
import { useChatStore } from "@/store/chat-store";
import { ComplianceAssistantPanel } from "@/modules/roadmap/components/compliance-assistant-panel";
import { PathChoice, type PathChoiceValue } from "@/modules/roadmap/components/path-choice";
import { cn } from "@/lib/utils";
import { PageNavBar } from "@/components/layout/page-nav";

const VALID_GOALS = new Set(PROCESS_GOALS.map((g) => g.id));

type NewRoadmapFormProps = {
  initialGoal?: string;
  /** Restored after sign-in so a half-made choice isn't lost */
  initialSubCity?: string;
  initialHeld?: string[];
  initialChoice?: PathChoiceValue;
};

function FormStep({
  number,
  title,
  hint,
  children,
}: {
  number: number;
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="flex gap-3">
        <span className="bg-primary/10 text-primary flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold">
          {number}
        </span>
        <div className="min-w-0 flex-1 pt-0.5">
          <h2 className="text-base font-semibold">{title}</h2>
          {hint && (
            <p className="text-muted-foreground mt-1 text-sm">{hint}</p>
          )}
        </div>
      </div>
      <div className="overflow-visible pl-11">{children}</div>
    </section>
  );
}

export function NewRoadmapForm({ initialGoal, initialSubCity, initialHeld, initialChoice }: NewRoadmapFormProps) {
  const router = useRouter();
  const setCurrent = useRoadmapStore((s) => s.setCurrent);
  const { createRoadmap, isCreating } = useCreateRoadmap();
  const updateSlots = useChatStore((s) => s.updateSlots);

  const defaultGoal =
    initialGoal && VALID_GOALS.has(initialGoal) ? initialGoal : "passport";
  const [goal, setGoal] = useState(defaultGoal);
  const [subCity, setSubCity] = useState(initialSubCity || "bole");
  const [documentsHeld, setDocumentsHeld] = useState<string[]>(
    (initialHeld ?? []).filter((d) => (ALL_DOCUMENT_IDS as readonly string[]).includes(d)),
  );
  // Step 2 of the flow: "do it myself" or "hire an agent"
  const [stage, setStage] = useState<"details" | "choose">(initialChoice ? "choose" : "details");
  const [choice, setChoice] = useState<PathChoiceValue | null>(initialChoice ?? null);
  const [showDocs, setShowDocs] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<"form" | "assistant">("form");

  const formSync = useMemo(
    () => ({
      goal,
      subCity,
      documentsHeld,
      onGoalChange: setGoal,
      onSubCityChange: setSubCity,
      onDocumentsChange: setDocumentsHeld,
    }),
    [goal, subCity, documentsHeld],
  );

  const syncToChatStore = useCallback(
    (partial: { goal?: string; sub_city?: string; documents_held?: string[] }) => {
      updateSlots(partial);
    },
    [updateSlots],
  );

  useEffect(() => {
    syncToChatStore({ goal, sub_city: subCity, documents_held: documentsHeld });
  }, [goal, subCity, documentsHeld, syncToChatStore]);

  const relevantDocs = useMemo(() => {
    const g = PROCESS_GOALS.find((x) => x.id === goal);
    if (!g) return [...ALL_DOCUMENT_IDS];
    const subCityLabel = getLocationLabel(subCity);
    const stepIds = new Set(g.getSteps(subCity, subCityLabel).map((s) => s.id));
    return ALL_DOCUMENT_IDS.filter((id) => stepIds.has(id));
  }, [goal, subCity]);

  function toggleDocument(id: string) {
    setDocumentsHeld((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    );
  }

  function handleGoalChange(next: string) {
    setGoal(next);
    syncToChatStore({ goal: next });
  }

  function handleSubCityChange(next: string) {
    setSubCity(next);
    syncToChatStore({ sub_city: next });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!roadmapRequestSchema.safeParse({ goal, subCity, documentsHeld }).success) return;
    setSubmitError(null);
    setStage("choose");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function generateRoadmap() {
    const parsed = roadmapRequestSchema.safeParse({ goal, subCity, documentsHeld });
    if (!parsed.success) return;
    setSubmitError(null);
    try {
      const roadmap = await createRoadmap(parsed.data);
      setCurrent(roadmap);
      router.push("/roadmap");
    } catch (err) {
      setSubmitError(
        err instanceof RoadmapApiError
          ? err.message
          : "Something went wrong. Try again.",
      );
    }
  }

  const goalLabel = PROCESS_GOALS.find((g) => g.id === goal)?.label ?? goal;
  const returnTo = `/roadmap/new?${new URLSearchParams({
    goal,
    sub: subCity,
    ...(documentsHeld.length ? { held: documentsHeld.join(",") } : {}),
    choice: "agent",
  }).toString()}`;

  const choicePanel = (
    <div className="px-4 py-8 md:py-10 lg:px-8">
      <PathChoice
        goal={goal}
        goalLabel={goalLabel}
        subCity={subCity}
        heldLabels={documentsHeld.map((id) => DOCUMENT_LABELS[id] ?? id)}
        choice={choice}
        onChoose={setChoice}
        onBack={() => setStage("details")}
        onShowSteps={generateRoadmap}
        isGenerating={isCreating}
        generateError={submitError}
        returnTo={returnTo}
      />
    </div>
  );

  const formPanel = (
    <div className="px-4 py-8 md:py-10 lg:px-8">
      <header className="mb-8 text-center md:text-left">
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          Find my path
        </h1>
        <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
          Use the form or chat with the assistant: English or Amharic.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="border-border space-y-10 overflow-visible rounded-xl border bg-card p-6 md:p-8"
      >
        <FormStep number={1} title="What do you need?">
          <GoalPicker value={goal} onChange={handleGoalChange} />
        </FormStep>

        <div className="border-border border-t" />

        <FormStep
          number={2}
          title="Where in Addis Ababa?"
          hint="Tap your area or search below."
        >
          <SubCityPicker value={subCity} onChange={handleSubCityChange} />
        </FormStep>

        <div className="border-border border-t" />

        <FormStep
          number={3}
          title="Already have documents?"
          hint="Optional, we skip steps you finished."
        >
          <button
            type="button"
            onClick={() => setShowDocs((s) => !s)}
            className="text-primary text-sm font-medium"
          >
            {showDocs ? "Hide list" : "Show list"}
            {documentsHeld.length > 0 &&
              ` (${documentsHeld.length} selected)`}
          </button>
          {showDocs && (
            <div className="mt-3 flex flex-wrap gap-2">
              {relevantDocs.map((id) => {
                const selected = documentsHeld.includes(id);
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => toggleDocument(id)}
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-xs font-medium",
                      selected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-background",
                    )}
                  >
                    {DOCUMENT_LABELS[id] ?? id}
                  </button>
                );
              })}
            </div>
          )}
        </FormStep>

        {submitError && (
          <p className="text-destructive text-center text-sm">{submitError}</p>
        )}

        <Button
          type="submit"
          size="lg"
          className="h-12 w-full rounded-lg text-base"
        >
          Continue →
        </Button>
      </form>
    </div>
  );

  return (
    <div className="mx-auto max-w-6xl">
      <PageNavBar label="Find my path" className="pb-2" />
      {/* Mobile tab switcher */}
      <div className="border-border flex border-b lg:hidden">
        <button
          type="button"
          onClick={() => setMobileTab("form")}
          className={cn(
            "flex-1 py-3 text-sm font-medium",
            mobileTab === "form"
              ? "border-primary text-primary border-b-2"
              : "text-muted-foreground",
          )}
        >
          Form
        </button>
        <button
          type="button"
          onClick={() => setMobileTab("assistant")}
          className={cn(
            "flex-1 py-3 text-sm font-medium",
            mobileTab === "assistant"
              ? "border-primary text-primary border-b-2"
              : "text-muted-foreground",
          )}
        >
          Assistant
        </button>
      </div>

      <div className="lg:grid lg:min-h-[calc(100dvh-var(--nav-h))] lg:grid-cols-[1fr_380px]">
        <div className={cn(mobileTab !== "form" && "hidden lg:block")}>
          {stage === "choose" ? choicePanel : formPanel}
        </div>
        <div
          className={cn(
            "lg:sticky lg:top-(--nav-h) lg:h-[calc(100dvh-var(--nav-h))]",
            mobileTab !== "assistant" && "hidden lg:block",
          )}
        >
          <ComplianceAssistantPanel formSync={formSync} />
        </div>
      </div>
    </div>
  );
}
