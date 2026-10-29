"use client";

import { StandaloneChatPanel } from "@/modules/chat/components/standalone-chat-panel";

/** Rendered inside the full-screen app shell (no footer), so it only has to fill its parent. */
export function ChatPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <StandaloneChatPanel />
    </div>
  );
}
