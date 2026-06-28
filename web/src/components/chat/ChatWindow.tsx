"use client";

import { useEffect, useRef } from "react";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";

const QUICK_REPLIES = [
  { label: "ፓስፖርት እፈልጋለሁ", text: "ፓስፖርት እፈልጋለሁ በቦሌ" },
  { label: "Trade license", text: "I need a trade license in Bole" },
  { label: "ንግድ ፈቃድ", text: "ንግድ ፈቃድ እፈልጋለሁ" },
  { label: "General advice", text: "What advice do you have for starting a business?" },
];

type ChatWindowProps = {
  messages: ChatMessage[];
  isLoading?: boolean;
  onQuickReply?: (text: string) => void;
};

export function ChatWindow({ messages, isLoading, onQuickReply }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      {messages.length === 0 && !isLoading && (
        <div className="space-y-3 pt-6">
          <p className="text-muted-foreground text-center text-xs">
            Tell me what you need — passport, trade license, TIN, or ask for advice.
          </p>
          {onQuickReply && (
            <div className="flex flex-wrap justify-center gap-2">
              {QUICK_REPLIES.map((q) => (
                <button
                  key={q.label}
                  type="button"
                  onClick={() => onQuickReply(q.text)}
                  className="border-border hover:bg-muted rounded-full border px-3 py-1 text-xs"
                >
                  {q.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {messages.map((msg) => (
        <div
          key={msg.id}
          className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}
        >
          <div
            className={cn(
              "max-w-[85%] rounded-sm px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap",
              msg.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-foreground",
            )}
          >
            {msg.text}
          </div>
        </div>
      ))}

      {isLoading && (
        <div className="flex justify-start">
          <div className="bg-muted rounded-sm px-3 py-2">
            <Spinner className="size-3" />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
