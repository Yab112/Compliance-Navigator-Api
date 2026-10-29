"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { type AssistantController, useAssistant } from "@/api/assistant";
import { ChatInput } from "@/components/chat/ChatInput";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { cn } from "@cn/core/lib/utils";
import type { AssistantAction, AssistantReply, AssistantWidget, StaffAuthor, TurnResult } from "@/types/assistant";
import { AssistantCards } from "@/components/assistant/assistant-cards";

type AssistantPanelProps = {
  /** Separates conversations, e.g. "ask" or "roadmap-new" */
  scope: string;
  title?: string;
  subtitle?: string;
  className?: string;
  onTurn?: (result: TurnResult) => void;
  /** What the page is about, e.g. "path:trade_license", so questions need no restating */
  contextService?: string | null;
  /** Extra controls in the header, e.g. the mobile "Contact us" button */
  headerExtra?: React.ReactNode;
};

type FormWidget = Extract<AssistantWidget, { kind: "form" }>;

/** Slot filling: the agent asks for several details at once (name, phone, what happened). */
function FormWidgetView({ widget, active, onAction }: { widget: FormWidget; active: boolean; onAction: (a: AssistantAction) => void }) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(widget.fields.map((f) => [f.key, f.value ?? ""])),
  );
  const [missing, setMissing] = useState<string[]>([]);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const empty = widget.fields.filter((f) => f.required && !values[f.key]?.trim()).map((f) => f.key);
    setMissing(empty);
    if (empty.length) return;
    const clean = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v.trim()]));
    const label = widget.fields
      .map((f) => clean[f.key])
      .filter(Boolean)
      .join(" · ");
    onAction({ type: "form", key: widget.key, value: clean, label: label.length > 160 ? `${label.slice(0, 157)}...` : label });
  };
  return (
    <form onSubmit={submit} className="border-border bg-card mt-2 space-y-2.5 rounded-md border p-3">
      <fieldset disabled={!active} className="space-y-2.5">
        {widget.fields.map((f) => {
          const id = `w-${widget.key}-${f.key}`;
          const invalid = missing.includes(f.key);
          const common = {
            id,
            value: values[f.key] ?? "",
            placeholder: f.placeholder ?? undefined,
            "aria-invalid": invalid || undefined,
            onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
              setValues((v) => ({ ...v, [f.key]: e.target.value })),
          };
          return (
            <div key={f.key} className="space-y-1">
              <label htmlFor={id} className="text-xs font-medium">
                {f.label}
                {f.required && <span className="text-destructive"> *</span>}
              </label>
              {f.type === "textarea" ? (
                <Textarea rows={3} {...common} />
              ) : (
                <Input type={f.type} inputMode={f.type === "tel" ? "tel" : undefined} {...common} />
              )}
              {invalid && <p className="text-destructive text-[11px]">Please fill this in</p>}
            </div>
          );
        })}
        <Button type="submit" size="sm">
          {widget.submit_label ?? "Continue"}
        </Button>
      </fieldset>
    </form>
  );
}

function Widget({ widget, active, onAction }: { widget: AssistantWidget; active: boolean; onAction: (a: AssistantAction) => void }) {
  if (widget.kind === "form") return <FormWidgetView widget={widget} active={active} onAction={onAction} />;
  return <OptionsWidget widget={widget} active={active} onAction={onAction} />;
}

function OptionsWidget({
  widget,
  active,
  onAction,
}: {
  widget: Exclude<AssistantWidget, FormWidget>;
  active: boolean;
  onAction: (a: AssistantAction) => void;
}) {
  const [selected, setSelected] = useState<string[]>(widget.selected ?? []);
  if (widget.kind === "checklist") {
    const toggle = (v: string) => setSelected((s) => (s.includes(v) ? s.filter((x) => x !== v) : [...s, v]));
    return (
      <fieldset disabled={!active} className="border-border bg-card mt-2 rounded-md border p-3">
        <ul className="space-y-1.5">
          {widget.options.map((o) => (
            <li key={o.value}>
              <label className="flex cursor-pointer items-start gap-2 text-sm">
                <input type="checkbox" className="accent-primary mt-0.5 size-4" checked={selected.includes(o.value)} onChange={() => toggle(o.value)} />
                <span>{o.label}</span>
              </label>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={() =>
              onAction({
                type: "documents",
                value: selected,
                label: widget.options.filter((o) => selected.includes(o.value)).map((o) => o.label).join(", ") || widget.none_label,
              })
            }
          >
            {widget.submit_label ?? "Continue"}
          </Button>
          {widget.none_label && (
            <Button size="sm" variant="outline" onClick={() => onAction({ type: "documents", value: [], label: widget.none_label })}>
              {widget.none_label}
            </Button>
          )}
        </div>
      </fieldset>
    );
  }
  return (
    <div className={cn("mt-2 flex flex-wrap gap-1.5", widget.kind === "sub_city" && "grid grid-cols-2 sm:grid-cols-3")}>
      {widget.options.map((o) => (
        <button
          key={o.value}
          type="button"
          disabled={!active}
          onClick={() => onAction({ type: "choice", key: widget.key, value: o.value, label: o.label })}
          className="border-primary/40 text-primary hover:bg-primary rounded-md border bg-white px-3 py-1.5 text-left text-sm font-medium transition-colors hover:text-white disabled:pointer-events-none disabled:opacity-50"
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function AssistantBubble({ reply, active, onAction }: { reply: AssistantReply; active: boolean; onAction: (a: AssistantAction) => void }) {
  return (
    <div className="flex max-w-[92%] gap-2 sm:max-w-[85%]">
      <span className="bg-primary mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white" aria-hidden>
        CN
      </span>
      <div className="min-w-0 flex-1">
        <div className="bg-secondary/70 rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-line">{reply.text}</div>
        {reply.source && <p className="text-muted-foreground mt-1 px-1 text-[11px]">{reply.source}</p>}
        <AssistantCards cards={reply.cards} />
        {reply.widget && <Widget widget={reply.widget} active={active} onAction={onAction} />}
        {reply.actions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {reply.actions.map((a, i) =>
              a.kind === "link" ? (
                <Link key={i} href={a.href} className="bg-primary rounded-md px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary/90">
                  {a.label}
                </Link>
              ) : (
                <button
                  key={i}
                  type="button"
                  disabled={!active}
                  onClick={() => onAction({ ...a.action, label: a.label })}
                  className="border-primary text-primary rounded-md border px-3 py-1.5 text-xs font-semibold hover:bg-secondary disabled:opacity-50"
                >
                  {a.label}
                </button>
              ),
            )}
          </div>
        )}
        {active && reply.quick_replies.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {reply.quick_replies.map((q, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onAction(q.action.type === "message" ? q.action : { ...q.action, label: q.label })}
                className="border-border hover:border-primary hover:text-primary rounded-full border bg-white px-3 py-1 text-xs transition-colors"
              >
                {q.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** A reply typed by a person on the support team, not the bot. */
function StaffBubble({ text, staff }: { text: string; staff: StaffAuthor }) {
  return (
    <div className="flex max-w-[92%] gap-2 sm:max-w-[85%]">
      <span
        className="bg-gov-yellow text-gov-ink mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-[9px] font-bold"
        aria-hidden
      >
        HELP
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-gov-ink mb-0.5 px-1 text-[11px] font-semibold">
          {staff.name || "Support"}
          {staff.team && <span className="text-muted-foreground font-normal"> · {staff.team} team</span>}
        </p>
        <div className="border-gov-yellow bg-gov-yellow/10 rounded-2xl rounded-tl-sm border px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-line">
          {text}
        </div>
      </div>
    </div>
  );
}

function Typing() {
  return (
    <div className="flex gap-2" aria-live="polite" aria-label="Assistant is typing">
      <span className="bg-primary flex size-7 items-center justify-center rounded-full text-[11px] font-bold text-white">CN</span>
      <span className="bg-secondary/70 flex items-center gap-1 rounded-2xl rounded-tl-sm px-4 py-3">
        {[0, 1, 2].map((i) => (
          <span key={i} className="bg-primary/60 size-1.5 animate-bounce rounded-full" style={{ animationDelay: `${i * 150}ms` }} />
        ))}
      </span>
    </div>
  );
}

export function AssistantPanel({ scope, onTurn, contextService, ...view }: AssistantPanelProps) {
  const assistant = useAssistant(scope, { onTurn, contextService });
  return <AssistantPanelView assistant={assistant} {...view} />;
}

type AssistantPanelViewProps = Omit<AssistantPanelProps, "scope" | "onTurn" | "contextService"> & {
  assistant: AssistantController;
};

/** The chat itself, driven by a controller so the page around it can also send messages. */
export function AssistantPanelView({ assistant, title = "Compliance Assistant", subtitle, className, headerExtra }: AssistantPanelViewProps) {
  const { messages, language, pending, error, channel, ticket, send, startOver, switchLanguage } = assistant;
  const am = language === "am";
  const endRef = useRef<HTMLDivElement>(null);
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant")?.id;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  const onAction = (action: AssistantAction) => {
    if (action.type === "start_over") return void startOver();
    if (action.type === "message") return void send({ message: action.value });
    void send({ action });
  };

  return (
    <div className={cn("bg-background flex h-full min-h-[420px] flex-col", className)}>
      <div className="border-border bg-card flex shrink-0 flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-gov-ink truncate text-sm font-semibold">{title}</h2>
          <p className="text-muted-foreground truncate text-xs">{subtitle ?? "English or Amharic · type or speak"}</p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-1">
          <div className="border-border flex overflow-hidden rounded-md border text-xs" role="group" aria-label="Language">
            {(["en", "am"] as const).map((l) => (
              <button
                key={l}
                type="button"
                aria-pressed={language === l}
                onClick={() => switchLanguage(l)}
                className={cn("px-2 py-1", language === l ? "bg-primary text-white" : "hover:bg-secondary")}
              >
                {l === "en" ? "EN" : "አማ"}
              </button>
            ))}
          </div>
          {channel !== "human" && (
            <Button
              variant="outline"
              size="sm"
              disabled={pending}
              onClick={() => void send({ action: { type: "handoff", label: am ? "ሰው ማነጋገር እፈልጋለሁ" : "Talk to a person" } })}
              title={am ? "ጥያቄዎን ለድጋፍ ቡድናችን ያስተላልፉ" : "Hand this conversation to our support team"}
            >
              {am ? "ሰው ያነጋግሩ" : "Talk to a person"}
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => void startOver()}>
            {am ? "እንደገና" : "Start over"}
          </Button>
          {headerExtra}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-4 sm:px-4" role="log" aria-live="polite">
        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="flex justify-end">
              <p className="bg-primary max-w-[85%] rounded-2xl rounded-tr-sm px-3.5 py-2 text-sm whitespace-pre-line text-white">{m.text}</p>
            </div>
          ) : m.role === "staff" ? (
            <StaffBubble key={m.id} text={m.text} staff={m.staff} />
          ) : (
            <AssistantBubble key={m.id} reply={m.reply} active={m.id === lastAssistant && !pending} onAction={onAction} />
          ),
        )}
        {pending && channel !== "human" && <Typing />}
        {error && <p className="text-destructive text-center text-xs">{error}</p>}
        <div ref={endRef} />
      </div>

      {ticket && (
        <div
          className={cn(
            "border-border flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t px-4 py-2 text-xs",
            channel === "human" ? "bg-gov-yellow/15" : "bg-secondary/50",
          )}
          role="status"
        >
          <p className="min-w-0">
            {channel === "human" ? (
              <>
                <span className="font-semibold">
                  {am ? `ከ${ticket.queue_label} ቡድን ጋር እየተነጋገሩ ነው` : `You're talking with the ${ticket.queue_label} team`}
                </span>
                <span className="text-muted-foreground"> · {ticket.ref} · {ticket.status_label}</span>
              </>
            ) : (
              <span className="text-muted-foreground">
                {am ? "የድጋፍ ጥያቄ" : "Support request"} {ticket.ref} · {ticket.queue_label} · {ticket.status_label}
              </span>
            )}
          </p>
          {channel === "human" ? (
            <button
              type="button"
              disabled={pending}
              className="text-primary font-semibold hover:underline disabled:opacity-50"
              onClick={() => void send({ action: { type: "channel", value: "agent", label: am ? "ወደ ረዳቱ ተመለስ" : "Back to the assistant" } })}
            >
              {am ? "ወደ ረዳቱ ተመለስ" : "Back to the assistant"}
            </button>
          ) : (
            !["resolved", "closed"].includes(ticket.status) && (
              <button
                type="button"
                disabled={pending}
                className="text-primary font-semibold hover:underline disabled:opacity-50"
                onClick={() => void send({ action: { type: "channel", value: "human", label: am ? "ለቡድኑ ይጻፉ" : "Write to the team" } })}
              >
                {am ? "ለቡድኑ ይጻፉ" : "Write to the team"}
              </button>
            )
          )}
        </div>
      )}
      <ChatInput onSend={(text) => void send({ message: text })} disabled={pending} enableVoice />
    </div>
  );
}
