"use client";

import { StandaloneChatPanel } from "@/modules/chat/components/standalone-chat-panel";

export function ChatPage() {
  return (
    <div className="mx-auto flex h-[calc(100dvh-3.5rem)] max-w-2xl flex-col border-x">
      <StandaloneChatPanel />
    </div>
  );
}
