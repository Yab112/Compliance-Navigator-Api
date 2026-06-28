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

export function StandaloneChatPanel() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const router = useRouter();

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
          goal: slots.goal,
          sub_city: slots.sub_city,
          documents_held: slots.documents_held,
          conversation_history: conversationHistory,
        });

        addAssistantMessage(response.reply);
        updateHistory(response.updated_history ?? []);

        if (response.suggested_goal) updateSlots({ goal: response.suggested_goal });
        if (response.suggested_sub_city) updateSlots({ sub_city: response.suggested_sub_city });
        if (response.suggested_documents_held.length > 0)
          updateSlots({ documents_held: response.suggested_documents_held });

        if (response.roadmap) {
          setCurrent(response.roadmap);
          router.push("/roadmap");
        }
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
      slots,
      conversationHistory,
      updateHistory,
      updateSlots,
      setCurrent,
      router,
    ],
  );

  if (!isLoggedIn) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
        <p className="text-sm font-semibold">Compliance Assistant</p>
        <p className="text-muted-foreground max-w-xs text-xs leading-relaxed">
          Sign in to chat in English or Amharic. Ask about permits, licenses, IDs, or any
          government process — type or use your voice.
        </p>
        <Button asChild size="sm">
          <Link href="/login?returnTo=/chat">Sign in to chat</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-border flex shrink-0 items-center justify-between border-b px-4 py-3">
        <div>
          <p className="text-sm font-semibold">Compliance Assistant</p>
          <p className="text-muted-foreground text-xs">
            English or Amharic · type or speak · history saved
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={clearChat}>
          Clear
        </Button>
      </div>

      <ChatWindow messages={messages} isLoading={isSending} onQuickReply={handleSend} />

      <ChatInput onSend={handleSend} disabled={isSending} enableVoice />
    </div>
  );
}
