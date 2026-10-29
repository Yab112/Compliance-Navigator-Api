"use client";

import { useCallback } from "react";
import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { PROCESS_GOALS } from "@/data/process-graph";
import type { TurnResult } from "@/types/assistant";

const GOALS = new Set(PROCESS_GOALS.map((g) => g.id));

export type FormSyncProps = {
  goal: string;
  subCity: string;
  documentsHeld: string[];
  onGoalChange: (goal: string) => void;
  onSubCityChange: (subCity: string) => void;
  onDocumentsChange: (docs: string[]) => void;
};

type ComplianceAssistantPanelProps = {
  formSync: FormSyncProps;
  compact?: boolean;
};

/** Find-my-path side panel: what the assistant learns fills the form next to it. */
export function ComplianceAssistantPanel({ formSync, compact = false }: ComplianceAssistantPanelProps) {
  const { onGoalChange, onSubCityChange, onDocumentsChange } = formSync;
  const onTurn = useCallback(
    (result: TurnResult) => {
      const key = result.service?.key ?? "";
      if (result.subCity) onSubCityChange(result.subCity);
      // Only guided paths map onto this form; other services stay in the chat
      if (key.startsWith("path:") && GOALS.has(key.slice(5))) {
        onGoalChange(key.slice(5));
        if (result.held.length) onDocumentsChange(result.held);
      }
    },
    [onGoalChange, onSubCityChange, onDocumentsChange],
  );
  return (
    <AssistantPanel
      scope="roadmap-new"
      onTurn={onTurn}
      contextService={formSync.goal ? `path:${formSync.goal}` : null}
      className={compact ? "min-h-[320px]" : "border-border border-l"}
    />
  );
}
