"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { useChatStore } from "@/store/chat-store";
import { useRoadmapStore } from "@/store/roadmap-store";
import { useSendMessage, ChatApiError } from "@/api/chat";
import { getAccessToken } from "@/lib/auth-token";

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

export function ComplianceAssistantPanel({
  formSync,
  compact = false,
}: ComplianceAssistantPanelProps) {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    setIsLoggedIn(!!getAccessToken());
  }, []);

  const {
    messages,
    conversationHistory,
    slots,
    addUserMessage,
    addAssistantMessage,
    updateHistory,
    updateSlots,
    clearChat,
  } = useChatStore();

  const setCurrent = useRoadmapStore((s) => s.setCurrent);
  const { sendMessage, isSending } = useSendMessage();

  const handleSend = useCallback(
    async (text: string) => {
      if (!isLoggedIn) return;

      addUserMessage(text);

      try {
        const response = await sendMessage({
          message: text,
          goal: formSync.goal,
          documents_held: formSync.documentsHeld,
          sub_city: formSync.subCity,
          conversation_history: conversationHistory,
        });

        addAssistantMessage(response.reply);
        updateHistory(response.updated_history ?? []);

        if (response.suggested_goal) {
          formSync.onGoalChange(response.suggested_goal);
          updateSlots({ goal: response.suggested_goal });
        }
        if (response.suggested_sub_city) {
          formSync.onSubCityChange(response.suggested_sub_city);
          updateSlots({ sub_city: response.suggested_sub_city });
        }
        if (response.suggested_documents_held.length > 0) {
          formSync.onDocumentsChange(response.suggested_documents_held);
          updateSlots({ documents_held: response.suggested_documents_held });
        }

        if (response.roadmap) {
          setCurrent(response.roadmap);
          router.push("/roadmap");
        }
      } catch (err) {
        const msg =
          err instanceof ChatApiError
            ? err.message
            : "Something went wrong. Please try again.";
        addAssistantMessage(msg);
      }
    },
    [
      isLoggedIn,
      addUserMessage,
      addAssistantMessage,
      sendMessage,
      formSync,
      conversationHistory,
      updateHistory,
      updateSlots,
      setCurrent,
      router,
    ],
  );

  const handleQuickReply = useCallback(
    (text: string) => {
      handleSend(text);
    },
    [handleSend],
  );

  if (!isLoggedIn) {
    return (
      <div
        className={
          compact
            ? "flex flex-col items-center justify-center gap-3 p-6 text-center"
            : "border-border flex h-full flex-col items-center justify-center gap-4 border-l p-6 text-center"
        }
      >
        <p className="text-sm font-medium">Compliance Assistant</p>
        <p className="text-muted-foreground max-w-xs text-xs leading-relaxed">
          Sign in to chat — ask in English or Amharic, type or use voice.
          The form works without an account.
        </p>
        <Button asChild size="sm">
          <Link href="/login?returnTo=/roadmap/new">Sign in to chat</Link>
        </Button>
      </div>
    );
  }

  return (
    <div
      className={
        compact
          ? "flex h-full min-h-[320px] flex-col"
          : "border-border flex h-full flex-col border-l"
      }
    >
      <div className="border-border flex shrink-0 items-center justify-between border-b px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">Compliance Assistant</h2>
          <p className="text-muted-foreground text-xs">
            English or Amharic · type or speak
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={clearChat}>
          Clear
        </Button>
      </div>

      <ChatWindow
        messages={messages}
        isLoading={isSending}
        onQuickReply={handleQuickReply}
      />

      <ChatInput onSend={handleSend} disabled={isSending} enableVoice />
    </div>
  );
}
