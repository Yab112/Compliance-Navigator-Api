import { cn } from "@cn/core/lib/utils";
import { formatDateTime } from "@cn/core/lib/format";
import type { TicketMessage } from "@cn/core/types/support";

const WHO: Record<TicketMessage["author_kind"], string> = {
  customer: "Customer",
  staff: "Support team",
  system: "System",
  assistant: "Assistant",
};

/** A ticket conversation. `viewer` decides which side is "mine"; internal notes only reach staff. */
export function TicketThread({ messages, viewer }: { messages: TicketMessage[]; viewer: "customer" | "staff" }) {
  if (!messages.length) return <p className="text-muted-foreground text-sm">No messages yet.</p>;
  return (
    <ol className="space-y-3">
      {messages.map((m) => {
        if (m.author_kind === "system") {
          return (
            <li key={m.id} className="text-muted-foreground text-center text-[11px]">
              {m.body} · {formatDateTime(m.created_at)}
            </li>
          );
        }
        const mine = viewer === "customer" ? m.author_kind === "customer" : m.author_kind === "staff";
        return (
          <li key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
            <div className="max-w-[88%]">
              <p className={cn("text-muted-foreground mb-0.5 px-1 text-[11px]", mine && "text-right")}>
                <span className="text-foreground font-medium">
                  {viewer === "customer" && m.author_kind === "customer" ? "You" : (m.author_name ?? WHO[m.author_kind])}
                </span>
                {m.internal && <span className="ml-1.5 rounded bg-amber-200 px-1 text-[10px] font-semibold text-amber-900">Internal note</span>}
                {" · "}
                {formatDateTime(m.created_at)}
              </p>
              <div
                className={cn(
                  "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed break-words whitespace-pre-line",
                  m.internal
                    ? "border border-dashed border-amber-400 bg-amber-50"
                    : mine
                      ? "bg-primary rounded-tr-sm text-white"
                      : m.author_kind === "staff"
                        ? "border-gov-yellow bg-gov-yellow/10 rounded-tl-sm border"
                        : "bg-secondary/70 rounded-tl-sm",
                )}
              >
                {m.body}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
