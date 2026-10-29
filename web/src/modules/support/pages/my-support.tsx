"use client";

import Link from "next/link";
import { useState } from "react";
import { MY_TICKETS_PAGE_SIZE, useMyTicket, useMyTickets, useSupportWrite } from "@/api/support";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@/components/ui/button";
import { Pager, useUrlPage } from "@/components/ui/pager";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/errors";
import { formatDateTime, timeAgo } from "@/modules/admin/shared/format";
import { EmptyState, ErrorState, LoadingState } from "@/modules/guday/components/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { ContactForm } from "@/modules/support/components/contact-form";
import { TicketStatusBadge } from "@/modules/support/components/ticket-badges";
import { TicketThread } from "@/modules/support/components/ticket-thread";

/** /account/support: every request the person sent to the support team. */
export function MySupport() {
  const gate = useAuthGate();
  const [page, setPage] = useUrlPage();
  const { data, isLoading, isError, error, refetch } = useMyTickets(page);
  const [writing, setWriting] = useState(false);
  const items = data?.payload.items ?? [];

  return (
    <PageShell
      title="My support requests · የድጋፍ ጥያቄዎቼ"
      description="Questions you sent to our team, from the assistant or the contact form. Replies appear here and in the chat."
      maxWidth="lg"
    >
      <div className="mb-4 flex flex-wrap gap-2">
        <Button onClick={() => setWriting((w) => !w)} variant={writing ? "outline" : "default"}>
          {writing ? "Close" : "Write to our team"}
        </Button>
        <Link
          href="/chat"
          className="border-border hover:border-primary rounded-md border px-3 py-2 text-sm"
        >
          Ask the assistant
        </Link>
      </div>
      {writing && (
        <div className="border-border bg-card mb-6 rounded-md border p-4">
          <ContactForm
            onSent={() => {
              // New requests come first
              if (page) setPage(0);
              else void refetch();
            }}
          />
        </div>
      )}
      {gate !== "ready" || isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState
          message={error?.message ?? "Could not load your requests"}
          onRetry={() => refetch()}
        />
      ) : !items.length ? (
        <EmptyState title="No requests yet">
          <p>
            When the assistant can&apos;t settle something, it hands it to a person and the request
            appears here.
          </p>
        </EmptyState>
      ) : (
        <>
          <ul className="divide-border border-border bg-card divide-y rounded-md border">
            {items.map((t) => (
              <li key={t.id}>
                <Link href={`/account/support/${t.id}`} className="hover:bg-secondary/40 block p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-muted-foreground font-mono text-xs">{t.ref}</span>
                    <TicketStatusBadge status={t.status} label={t.status_label} />
                  </div>
                  <p className="mt-1 font-semibold">{t.subject}</p>
                  <p className="text-muted-foreground mt-0.5 text-xs">
                    {t.queue_label} · sent {formatDateTime(t.created_at)} · updated{" "}
                    {timeAgo(t.updated_at)}
                  </p>
                  {t.last_message_preview && (
                    <p className="text-muted-foreground mt-1 line-clamp-1 text-sm">
                      {t.last_message_preview}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
          <Pager
            page={page}
            pageSize={MY_TICKETS_PAGE_SIZE}
            total={data?.payload.total ?? 0}
            onPage={setPage}
          />
        </>
      )}
    </PageShell>
  );
}

/** /account/support/[id]: the thread with the team and a reply box. */
export function MySupportTicket({ id }: { id: string }) {
  const gate = useAuthGate();
  const { data, isLoading, isError, error, refetch } = useMyTicket(id);
  const { reply, isPending } = useSupportWrite();
  const [body, setBody] = useState("");
  const [failure, setFailure] = useState<string | null>(null);
  const thread = data?.payload;
  const t = thread?.ticket;

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setFailure(null);
    try {
      await reply(id, body.trim());
      setBody("");
      void refetch();
    } catch (err) {
      setFailure(getErrorMessage(err, "Your reply wasn't sent. Please try again."));
    }
  };

  return (
    <PageShell title={t ? `${t.ref} · ${t.subject}` : "Support request · የድጋፍ ጥያቄ"} maxWidth="lg">
      {gate !== "ready" || isLoading ? (
        <LoadingState />
      ) : isError || !t ? (
        <ErrorState
          message={error?.message ?? "This request was not found"}
          onRetry={() => refetch()}
        />
      ) : (
        <div className="space-y-5">
          <div className="border-border bg-card flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md border p-4 text-sm">
            <TicketStatusBadge status={t.status} label={t.status_label} />
            <span>
              <span className="text-muted-foreground">Team:</span> {t.queue_label}
            </span>
            <span>
              <span className="text-muted-foreground">Sent:</span> {formatDateTime(t.created_at)}
            </span>
            {t.service_title && (
              <span>
                <span className="text-muted-foreground">About:</span> {t.service_title}
              </span>
            )}
          </div>
          <TicketThread messages={thread.messages.filter((m) => !m.internal)} viewer="customer" />
          <form onSubmit={send} className="border-border bg-card space-y-2 rounded-md border p-4">
            <label htmlFor="reply" className="text-sm font-medium">
              {t.status === "resolved" || t.status === "closed"
                ? "Still need help? Writing again reopens the request."
                : "Reply to the team · መልስ"}
            </label>
            <Textarea
              id="reply"
              rows={3}
              value={body}
              maxLength={4000}
              onChange={(e) => setBody(e.target.value)}
            />
            {failure && (
              <p className="text-destructive text-xs" role="alert">
                {failure}
              </p>
            )}
            <Button type="submit" disabled={!body.trim()} loading={isPending}>
              Send reply
            </Button>
          </form>
        </div>
      )}
    </PageShell>
  );
}
