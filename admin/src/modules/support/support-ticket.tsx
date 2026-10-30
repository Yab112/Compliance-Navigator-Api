"use client";

import Link from "next/link";
import { useState } from "react";
import { useCannedReplies, useSupportCustomer, useSupportDesk, useSupportTicket } from "@cn/core/api/support";
import { Button } from "@cn/ui/button";
import { Textarea } from "@cn/ui/textarea";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { formatDate, formatDateTime, humanize, timeAgo } from "@cn/core/lib/format";
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

/** Pick a saved reply for this ticket's team; it arrives filled in and can still be edited. */
function CannedPicker({ ticketId, onPick }: { ticketId: string; onPick: (text: string, id: string) => void }) {
  const { payload, isLoading, error } = useCannedReplies({ ticketId, limit: 100 });
  const items = payload?.items ?? [];
  if (error) return <span className="text-muted-foreground text-[11px]">Saved replies could not be loaded</span>;
  return (
    <NativeSelect
      aria-label="Insert a saved reply"
      value=""
      disabled={isLoading || !items.length}
      onChange={(e) => {
        const r = items.find((i) => i.id === e.target.value);
        if (r) onPick(r.rendered ?? r.body, r.id);
      }}
    >
      <option value="">{isLoading ? "Loading saved replies…" : items.length ? "Insert a saved reply…" : "No saved replies for this team"}</option>
      {items.map((r) => (
        <option key={r.id} value={r.id}>
          {r.title}
        </option>
      ))}
    </NativeSelect>
  );
}

function ReplyBox({ ticket }: { ticket: SupportTicket }) {
  const { reply, isPending } = useSupportDesk();
  const [body, setBody] = useState("");
  const [cannedId, setCannedId] = useState<string | null>(null);
  const [internal, setInternal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fromChat = !!ticket.conversation_id;
  const done = ticket.status === "resolved" || ticket.status === "closed";

  // One request: the reply and the resolve succeed or fail together, so a retry never sends it twice
  const send = async (resolve: boolean) => {
    if (!body.trim() || isPending) return;
    setError(null);
    try {
      await reply(ticket.id, body.trim(), internal, { resolve: resolve && !internal, cannedReplyId: internal ? null : cannedId });
      setBody("");
      setCannedId(null);
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
        <div className="flex flex-wrap items-center gap-3">
          {!internal && (
            <CannedPicker
              ticketId={ticket.id}
              onPick={(text, id) => {
                setBody((b) => (b.trim() ? `${b.trimEnd()}\n\n${text}` : text));
                setCannedId(id);
              }}
            />
          )}
          <label className="flex items-center gap-1.5 text-xs">
            <input type="checkbox" className="accent-primary size-3.5" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
            Internal note
          </label>
        </div>
      </div>
      <Textarea
        id="staff-reply"
        rows={5}
        value={body}
        maxLength={4000}
        aria-invalid={!!error}
        aria-describedby={error ? "staff-reply-error" : undefined}
        onChange={(e) => setBody(e.target.value)}
      />
      {!internal && (
        <p className="text-muted-foreground text-[11px]">
          {fromChat
            ? "They see this in their chat and their notification bell."
            : ticket.user_id
              ? "They see this in their account and their notification bell."
              : `They aren't signed in: also call or email them (${ticket.contact_phone || ticket.contact_email || "no contact given"}).`}
        </p>
      )}
      {error && (
        <p id="staff-reply-error" className="text-destructive text-xs" role="alert">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={!body.trim()} loading={isPending}>
          {internal ? "Add note" : "Send reply"}
        </Button>
        {!internal && !done && (
          <Button type="button" size="sm" variant="outline" disabled={!body.trim() || isPending} onClick={() => void send(true)}>
            Send and resolve
          </Button>
        )}
      </div>
    </form>
  );
}

const HIRE_STATUS: Record<string, string> = {
  open: "Waiting for a provider",
  requested: "Sent to provider",
  accepted: "Accepted",
  declined: "Declined",
  completed: "Delivered",
  confirmed: "Confirmed",
  cancelled: "Cancelled",
};

/** Who is behind the ticket: account, hires, payments, other requests. Loaded once, not polled. */
function CustomerBox({ ticketId }: { ticketId: string }) {
  const { payload: c, isLoading, error } = useSupportCustomer(ticketId);
  if (isLoading) {
    return (
      <Box title="This customer">
        <p className="text-muted-foreground text-xs">Loading…</p>
      </Box>
    );
  }
  if (error || !c) {
    return (
      <Box title="This customer">
        <p className="text-destructive text-xs">{getErrorMessage(error, "Could not load the customer")}</p>
      </Box>
    );
  }
  const acct = c.account;
  return (
    <Box title="This customer">
      {acct ? (
        <dl>
          <Row label="Account">{acct.name}</Row>
          <Row label="Email">{acct.email}</Row>
          <Row label="Phone">{acct.phone}</Row>
          <Row label="Joined">{formatDate(acct.created_at)}</Row>
          <Row label="Last sign-in">{acct.last_login_at ? timeAgo(acct.last_login_at) : "Never"}</Row>
          <Row label="Status">{acct.is_active ? "Active" : "Disabled"}</Row>
          <Row label="Roadmaps">{acct.roadmaps}</Row>
          <Row label="Provider">
            {c.provider && (
              <Link href={`/marketplace/${c.provider.id}`} className="text-primary hover:underline">
                {c.provider.display_name} ({humanize(c.provider.status)})
              </Link>
            )}
          </Row>
        </dl>
      ) : (
        <p className="text-muted-foreground text-xs">No account. Other requests below match the phone or email they gave.</p>
      )}

      {acct && c.hires && (
        <div className="mt-3">
          <h3 className="mb-1 text-xs font-medium">
            Hires ({c.hires.total}){" "}
            {c.hires.total > c.hires.items.length && <span className="text-muted-foreground font-normal">latest {c.hires.items.length}</span>}
          </h3>
          {c.hires.items.length ? (
            <ul className="divide-border divide-y text-xs">
              {c.hires.items.map((h) => (
                <li key={h.id} className="py-1">
                  <span className="block truncate font-medium">{h.title}</span>
                  <span className="text-muted-foreground">
                    {HIRE_STATUS[h.status] ?? humanize(h.status)}
                    {h.payment_status && h.payment_status !== "none" ? ` · ${humanize(h.payment_status)}` : ""}
                    {h.disputed ? ` · complaint ${h.dispute_status ?? ""}` : ""}
                    {h.provider_name ? ` · ${h.provider_name}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-xs">No hires.</p>
          )}
        </div>
      )}

      {acct && c.payments && (
        <div className="mt-3">
          <h3 className="mb-1 text-xs font-medium">Payments ({c.payments.total})</h3>
          {c.payments.items.length ? (
            <ul className="divide-border divide-y text-xs">
              {c.payments.items.map((p) => (
                <li key={p.tx_ref} className="flex justify-between gap-2 py-1">
                  <span className="min-w-0 truncate">{p.hire_title ?? p.tx_ref}</span>
                  <span className="shrink-0 tabular-nums">
                    {Number(p.amount).toLocaleString("en")} {p.currency} · {humanize(p.status)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-xs">No payments.</p>
          )}
        </div>
      )}
      {acct && c.hidden.length > 0 && (
        <p className="text-muted-foreground mt-2 text-[11px]">Your role does not show their {c.hidden.join(" and ")}.</p>
      )}

      <div className="mt-3">
        <h3 className="mb-1 text-xs font-medium">Other requests ({c.tickets.total})</h3>
        {c.tickets.items.length ? (
          <ul className="divide-border divide-y text-xs">
            {c.tickets.items.map((o) => (
              <li key={o.id} className="flex items-center justify-between gap-2 py-1">
                <Link href={`/support/${o.id}`} className="text-primary min-w-0 truncate hover:underline">
                  <span className="font-mono">{o.ref}</span> {o.subject}
                </Link>
                {/* Without a label the badge uses the staff wording ("Waiting on customer"), not the customer's */}
                <TicketStatusBadge status={o.status} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground text-xs">None.</p>
        )}
      </div>
    </Box>
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
        <ErrorState error={error} message={getErrorMessage(error)} onRetry={() => refetch()} />
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
            <TicketStatusBadge status={t.status} />
            {t.next_response_due_at && <SlaBadge due={t.next_response_due_at} overdue={t.overdue} done={done} />}
            {t.waiting_on === "us" && <span className="text-primary font-semibold">● Customer waiting for us {timeAgo(t.waiting_since)}</span>}
            {t.waiting_on === "customer" && <span className="text-muted-foreground">Waiting for the customer since {timeAgo(t.waiting_since)}</span>}
            <span className="text-muted-foreground">Opened {timeAgo(t.created_at)}</span>
            {t.follow_up_of && (
              <Link href={`/support/${t.follow_up_of}`} className="text-primary hover:underline">
                Follows up {t.follow_up_of_ref}
              </Link>
            )}
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
          <CustomerBox ticketId={t.id} />
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
              <Row label="First reply due">{formatDateTime(t.sla_due_at)}</Row>
              <Row label="First reply">{t.first_response_at ? formatDateTime(t.first_response_at) : "Not yet"}</Row>
              <Row label="Reply due now">{t.next_response_due_at && formatDateTime(t.next_response_due_at)}</Row>
              <Row label="Resolved">{t.resolved_at && formatDateTime(t.resolved_at)}</Row>
              <Row label="Messages">{t.message_count}</Row>
            </dl>
          </Box>
        </aside>
      </div>
    </AdminPage>
  );
}
