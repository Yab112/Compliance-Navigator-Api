"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { useRoadmapChatStore } from "@/store/roadmap-chat-store";
import { useSendMessage, ChatApiError } from "@/api/chat";
import { getAccessToken } from "@/lib/auth-token";
import type { Roadmap } from "@/types/roadmap";

type RoadmapChatPanelProps = {
  roadmap: Roadmap;
};

export function RoadmapChatPanel({ roadmap }: RoadmapChatPanelProps) {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    setIsLoggedIn(!!getAccessToken());
  }, []);

  const {
    messages,
    conversationHistory,
    addUserMessage,
    addAssistantMessage,
    updateHistory,
    clearChat,
  } = useRoadmapChatStore();

  const { sendMessage, isSending } = useSendMessage();

  const completed = roadmap.steps.filter((s) => s.status === "completed").length;
  const active = roadmap.steps.find((s) => s.status === "active");

  const handleSend = useCallback(
    async (text: string) => {
      if (!isLoggedIn) return;
      addUserMessage(text);

      try {
        const response = await sendMessage({
          message: text,
          goal: roadmap.request.goal,
          sub_city: roadmap.request.subCity,
          documents_held: roadmap.request.documentsHeld ?? [],
          conversation_history: conversationHistory,
        });

        addAssistantMessage(response.reply);
        updateHistory(response.updated_history ?? []);
      } catch (err) {
        addAssistantMessage(
          err instanceof ChatApiError ? err.message : "Something went wrong. Please try again.",
        );
      }
    },
    [
      isLoggedIn,
      addUserMessage,
      addAssistantMessage,
      sendMessage,
      roadmap,
      conversationHistory,
      updateHistory,
    ],
  );

  if (!isLoggedIn) {
    return (
      <div className="border-border flex h-full flex-col items-center justify-center gap-4 border-l p-6 text-center">
        <p className="text-sm font-semibold">Compliance Assistant</p>
        <p className="text-muted-foreground max-w-xs text-xs leading-relaxed">
          Sign in to ask questions about your roadmap — steps, fees, documents, or a different process.
        </p>
        <Button asChild size="sm">
          <Link href="/login?returnTo=/roadmap">Sign in to chat</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="border-border flex h-full flex-col border-l">
      {/* Header */}
      <div className="border-border flex shrink-0 items-center justify-between border-b px-4 py-3">
        <div>
          <p className="text-sm font-semibold">Compliance Assistant</p>
          <p className="text-muted-foreground text-xs">English or Amharic · type or speak</p>
        </div>
        <Button variant="ghost" size="sm" onClick={clearChat}>
          Clear
        </Button>
      </div>

      {/* Context card */}
      <div className="border-border bg-muted/40 shrink-0 space-y-1 border-b px-4 py-3">
        <p className="text-xs font-medium">
          {roadmap.request.goalLabel} · {roadmap.request.subCityLabel}
        </p>
        <p className="text-muted-foreground text-xs">
          {completed} of {roadmap.steps.length} steps done
          {active ? ` · next: ${active.office?.name ?? active.issuingAuthority}` : " · all done!"}
        </p>
        <p className="text-muted-foreground text-xs leading-relaxed pt-1">
          Ask about any step, required documents, fees, or start a different request.
        </p>
      </div>

      <ChatWindow messages={messages} isLoading={isSending} onQuickReply={handleSend} />

      <ChatInput onSend={handleSend} disabled={isSending} enableVoice />
    </div>
  );
}
