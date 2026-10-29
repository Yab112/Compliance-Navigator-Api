"use client";

import { AssistantPanel } from "@/components/assistant/assistant-panel";
import type { Roadmap } from "@/types/roadmap";

type RoadmapChatPanelProps = {
  roadmap: Roadmap;
};

/** Side panel on a saved path: one conversation per roadmap. */
export function RoadmapChatPanel({ roadmap }: RoadmapChatPanelProps) {
  return (
    <AssistantPanel
      scope={`roadmap-${roadmap.id}`}
      contextService={roadmap.request?.goal ? `path:${roadmap.request.goal}` : null}
      title="Questions about this path"
      subtitle="Fees, documents, offices, or hire an agent"
      className="border-border border-l"
    />
  );
}
