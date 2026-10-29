"use client";

import { useState } from "react";
import { useSupportDesk, useSupportTicket } from "@cn/core/api/support";
import { Button } from "@cn/ui/button";
import { Textarea } from "@cn/ui/textarea";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { formatDateTime, humanize } from "@cn/core/lib/format";
import { NativeSelect } from "@/modules/shared/native-select";
import { ErrorState, LoadingState } from "@/modules/shared/states";
import { SlaBadge, TicketStatusBadge } from "@cn/ui/support/ticket-badges";
import { TicketThread } from "@cn/ui/support/ticket-thread";
import { useUserStore } from "@cn/core/store/user-store";
import {
  PRIORITY_LABELS,
  QUEUE_LABELS,
  STATUS_LABELS,
  type SupportQueue,
  type SupportTicket,
  type TicketPatch,
  type TicketPriority,
  type TicketStatus,
} from "@cn/core/types/support";

const SOURCE_LABELS: Record<string, string> = { assistant: "Hand-off from the assistant", contact_form: "Contact form", report: "Report" };

function Box({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-border bg-card border p-3">
      <h2 className="text-muted-foreground mb-2 text-[11px] font-medium tracking-wider uppercase">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  if (children == null || children === "" || children === false) return null;
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2 py-0.5 text-xs">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function answerText(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "");
}

function Controls({ ticket, staff }: { ticket: SupportTicket; staff: { id: string; name: string }[] }) {
  const me = useUserStore((s) => s.user);
  const { update, isPending } = useSupportDesk();
  const [error, setError] = useState<string | null>(null);
  const patch = async (body: TicketPatch) => {
    setError(null);
    try {
      await update(ticket.id, body);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  return (
    <Box title="Handle">
      <div className="grid gap-2 text-xs">
        <label className="grid gap-1">
          <span className="text-muted-foreground">Status</span>
          <NativeSelect value={ticket.status} disabled={isPending} onChange={(e) => patch({ status: e.target.value as TicketStatus })}>
            {(Object.keys(STATUS_LABELS) as TicketStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="grid gap-1">
          <span className="text-muted-foreground">Priority</span>
          <NativeSelect value={ticket.priority} disabled={isPending} onChange={(e) => patch({ priority: e.target.value as TicketPriority })}>
            {(Object.keys(PRIORITY_LABELS) as TicketPriority[]).map((p) => (
              <option key={p} value={p}>
                {PRIORITY_LABELS[p]}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="grid gap-1">
          <span className="text-muted-foreground">Queue</span>
          <NativeSelect value={ticket.queue} disabled={isPending} onChange={(e) => patch({ queue: e.target.value as SupportQueue })}>
            {(Object.keys(QUEUE_LABELS) as SupportQueue[]).map((q) => (
              <option key={q} value={q}>
                {QUEUE_LABELS[q]}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="grid gap-1">
          <span className="text-muted-foreground">Assignee</span>
          <NativeSelect
            value={ticket.assignee_id ?? ""}
            disabled={isPending}
            onChange={(e) => patch({ assignee_id: e.target.value || null })}
          >
            <option value="">Unassigned</option>
            {staff.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </NativeSelect>
        </label>
        {me && ticket.assignee_id !== me.id && (
          <Button size="sm" variant="outline" loading={isPending} onClick={() => patch({ assignee_id: me.id })}>
            Assign to me
          </Button>
        )}
        {error && <p className="text-destructive">{error}</p>}
      </div>
    </Box>
  );
}

function ReplyBox({ ticket }: { ticket: SupportTicket }) {
  const { reply, update, isPending } = useSupportDesk();
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fromChat = !!ticket.conversation_id;

  const send = async (resolve: boolean) => {
    if (!body.trim()) return;
    setError(null);
    try {
      await reply(ticket.id, body.trim(), internal);
      if (resolve && !internal) await update(ticket.id, { status: "resolved" });
      setBody("");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void send(false);
      }}
      className={cn("border-border space-y-2 border p-3", internal ? "border-dashed border-amber-400 bg-amber-50" : "bg-card")}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor="staff-reply" className="text-xs font-medium">
          {internal ? "Internal note (only staff see this)" : "Reply to the customer"}
        </label>
        <label className="flex items-center gap-1.5 text-xs">
          <input type="checkbox" className="accent-primary size-3.5" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
          Internal note
        </label>
      </div>
      <Textarea id="staff-reply" rows={4} value={body} maxLength={4000} onChange={(e) => setBody(e.target.value)} />
      {!internal && (
        <p className="text-muted-foreground text-[11px]">
          {fromChat
            ? "They see this in their chat and their notification bell."
            : ticket.user_id
              ? "They see this in their account and their notification bell."
              : `They aren't signed in: also call or email them (${ticket.contact_phone || ticket.contact_email || "no contact given"}).`}
        </p>
      )}
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={!body.trim()} loading={isPending}>
          {internal ? "Add note" : "Send reply"}
        </Button>
        {!internal && (
          <Button type="button" size="sm" variant="outline" disabled={!body.trim() || isPending} onClick={() => void send(true)}>
            Send and resolve
          </Button>
        )}
      </div>
    </form>
  );
}

export function SupportTicketDetail({ id }: { id: string }) {
  const { payload, isLoading, error, refetch } = useSupportTicket(id);

  if (isLoading) {
    return (
      <AdminPage title="Support request">
        <LoadingState />
      </AdminPage>
    );
  }
  if (error || !payload) {
    return (
      <AdminPage title="Support request">
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      </AdminPage>
    );
  }

  const { ticket: t, messages, transcript, staff } = payload;
  const ctx = t.context ?? {};
  const done = t.status === "resolved" || t.status === "closed";

  return (
    <AdminPage
      title={`${t.ref} · ${t.subject}`}
      description={`${SOURCE_LABELS[t.source] ?? humanize(t.source)} · ${t.queue_label} · opened ${formatDateTime(t.created_at)}`}
    >
      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <TicketStatusBadge status={t.status} label={t.status_label} />
            {t.first_response_at ? (
              <span className="text-muted-foreground">First reply {formatDateTime(t.first_response_at)}</span>
            ) : (
              <SlaBadge due={t.sla_due_at} overdue={t.overdue} done={done} />
            )}
            {t.awaiting_staff && <span className="text-primary font-semibold">● Customer is waiting for us</span>}
          </div>
          <div className="border-border bg-background border p-4">
            <TicketThread messages={messages} viewer="staff" />
          </div>
          <ReplyBox ticket={t} />
          {transcript.length > 0 && (
            <details className="border-border bg-card border">
              <summary className="cursor-pointer px-3 py-2 text-xs font-medium">
                Chat with the assistant before the hand-off ({transcript.length} messages)
              </summary>
              <ol className="border-border max-h-[28rem] space-y-2 overflow-y-auto border-t p-3 text-xs">
                {transcript.map((m, i) => (
                  <li key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                    <div
                      className={cn(
                        "max-w-[85%] rounded-lg px-3 py-1.5 whitespace-pre-line",
                        m.role === "user" ? "bg-primary text-white" : m.role === "staff" ? "border-gov-yellow bg-gov-yellow/10 border" : "bg-secondary/70",
                      )}
                    >
                      <span className="block text-[10px] opacity-70">
                        {m.role === "user" ? "Customer" : m.role === "staff" ? "Staff" : "Assistant"} · {formatDateTime(m.created_at)}
                      </span>
                      {m.text}
                    </div>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </div>

        <aside className="space-y-3">
          <Controls ticket={t} staff={staff} />
          <Box title="Contact">
            <dl>
              <Row label="Name">{t.contact_name}</Row>
              <Row label="Phone">
                {t.contact_phone && (
                  <a href={`tel:${t.contact_phone}`} className="text-primary hover:underline">
                    {t.contact_phone}
                  </a>
                )}
              </Row>
              <Row label="Email">
                {t.contact_email && (
                  <a href={`mailto:${t.contact_email}`} className="text-primary hover:underline">
                    {t.contact_email}
                  </a>
                )}
              </Row>
              <Row label="Account">{t.user_email ?? (t.user_id ? "Signed in" : "Not signed in")}</Row>
            </dl>
          </Box>
          <Box title="What the assistant collected">
            <dl>
              <Row label="Summary">{ctx.summary}</Row>
              <Row label="Service">{t.service_title ?? ctx.service ?? t.service_key}</Row>
              <Row label="Sub-city">{ctx.sub_city && humanize(ctx.sub_city)}</Row>
              <Row label="Has already">{ctx.held?.length ? ctx.held.join(", ") : null}</Row>
              <Row label="Language">{ctx.language === "am" ? "Amharic" : ctx.language === "en" ? "English" : ctx.language}</Row>
              {Object.entries(ctx.answers ?? {}).map(([k, v]) => (
                <Row key={k} label={humanize(k)}>
                  {answerText(v)}
                </Row>
              ))}
            </dl>
            {!ctx.summary && !t.service_key && !ctx.service && !Object.keys(ctx.answers ?? {}).length && (
              <p className="text-muted-foreground text-xs">Nothing beyond the message itself.</p>
            )}
          </Box>
          <Box title="Facts">
            <dl>
              <Row label="Ref">
                <span className="font-mono">{t.ref}</span>
              </Row>
              <Row label="Source">{SOURCE_LABELS[t.source] ?? t.source}</Row>
              <Row label="Category">{t.category && humanize(t.category)}</Row>
              <Row label="Opened">{formatDateTime(t.created_at)}</Row>
              <Row label="Reply due">{formatDateTime(t.sla_due_at)}</Row>
              <Row label="Resolved">{t.resolved_at && formatDateTime(t.resolved_at)}</Row>
              <Row label="Messages">{t.message_count}</Row>
            </dl>
          </Box>
        </aside>
      </div>
    </AdminPage>
  );
}
