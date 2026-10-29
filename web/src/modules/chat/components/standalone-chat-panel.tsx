"use client";

import { useEffect, useState } from "react";
import { useAssistant } from "@/api/assistant";
import { AssistantPanelView } from "@/components/assistant/assistant-panel";
import { Button } from "@/components/ui/button";
import { ChatSidePanel } from "./chat-side-panel";

/** The Ask page: the assistant fills the screen, with contact options beside it (a drawer on phones). Works signed out. */
export function StandaloneChatPanel() {
  const assistant = useAssistant("ask");
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    if (!drawer) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [drawer]);

  return (
    <div className="mx-auto flex min-h-0 w-full max-w-6xl flex-1">
      <div className="border-border flex min-h-0 min-w-0 flex-1 flex-col lg:border-x">
        <AssistantPanelView
          assistant={assistant}
          className="min-h-0 flex-1"
          subtitle="Any service, any office · English or Amharic · type or speak"
          headerExtra={
            <Button variant="outline" size="sm" className="lg:hidden" aria-expanded={drawer} aria-controls="chat-help" onClick={() => setDrawer(true)}>
              Contact us · ያግኙን
            </Button>
          }
        />
      </div>
      <aside className="border-border hidden w-80 shrink-0 overflow-y-auto border-r lg:block" aria-label="Help and contact">
        <ChatSidePanel assistant={assistant} />
      </aside>

      {drawer && (
        <div className="fixed inset-0 z-[70] lg:hidden" role="dialog" aria-modal="true" aria-label="Help and contact" id="chat-help">
          <button type="button" aria-label="Close" className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
          <div className="bg-card absolute inset-y-0 right-0 flex w-[min(22rem,90vw)] flex-col shadow-xl">
            <div className="border-border flex shrink-0 items-center justify-between border-b px-4 py-3">
              <p className="text-sm font-semibold">Help and contact · እገዛ</p>
              <Button variant="ghost" size="sm" onClick={() => setDrawer(false)}>
                Close
              </Button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              <ChatSidePanel assistant={assistant} onPicked={() => setDrawer(false)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
