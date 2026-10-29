"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { type TicketFilters, useSupportSummary, useSupportTickets } from "@/api/support";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { AdminPage } from "@/modules/admin/components/admin-page";
import { timeAgo } from "@/modules/admin/shared/format";
import { NativeSelect } from "@/modules/admin/shared/native-select";
import { StatTile } from "@/modules/admin/shared/stat-tile";
import { EmptyState, ErrorState, LoadingState } from "@/modules/admin/shared/states";
import { useDebounced } from "@/modules/guday/components/shared";
import { PriorityBadge, SlaBadge, TicketStatusBadge } from "@/modules/support/components/ticket-badges";
import { PRIORITY_LABELS, QUEUE_LABELS, STATUS_LABELS, type SupportQueue, type TicketPriority, type TicketStatus } from "@/types/support";

const PAGE_SIZE = 25;
const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "active", label: "Active (new, open, waiting)" },
  ...(Object.keys(STATUS_LABELS) as TicketStatus[]).map((s) => ({ value: s, label: STATUS_LABELS[s] })),
];

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes == null) return "-";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  if (minutes < 1440) return `${(minutes / 60).toFixed(1)} h`;
  return `${(minutes / 1440).toFixed(1)} d`;
}

type View = { key: string; label: string; count?: number; overdue?: number; params: Record<string, string | null> };

export function SupportDesk() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const queue = params.get("queue") ?? "";
  const assigned = (params.get("assigned") ?? "") as "" | "me" | "none";
  const status = params.get("status") ?? "active";
  const priority = params.get("priority") ?? "";
  const page = Math.max(0, Number(params.get("page") ?? 0) || 0);
  const [query, setQuery] = useState(params.get("q") ?? "");
  const q = useDebounced(query.trim(), 300);

  const setParam = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== q) setParam({ q: q || null, page: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const summary = useSupportSummary();
  const filters: TicketFilters = {
    queue: queue || undefined,
    status,
    assigned: assigned || undefined,
    priority: priority || undefined,
    q: q || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  };
  const tickets = useSupportTickets(filters);
  const s = summary.payload;
  const t = s?.totals;
  const pages = Math.ceil((tickets.payload?.total ?? 0) / PAGE_SIZE);

  const views: View[] = [
    { key: "all", label: "All queues", count: t ? t.new + t.open + t.waiting_customer : undefined, overdue: t?.overdue, params: { queue: null, assigned: null } },
    { key: "me", label: "Assigned to me", count: t?.mine, params: { queue: null, assigned: "me" } },
    { key: "none", label: "Unassigned", count: t?.unassigned, params: { queue: null, assigned: "none" } },
    ...(s?.queues ?? (Object.keys(QUEUE_LABELS) as SupportQueue[]).map((key) => ({ key, label: QUEUE_LABELS[key], open: undefined, overdue: undefined }))).map(
      (qv) => ({ key: qv.key, label: qv.label, count: qv.open, overdue: qv.overdue, params: { queue: qv.key, assigned: null } }),
    ),
  ];
  const activeView = assigned || queue || "all";

  return (
    <AdminPage
      title="Support desk · የድጋፍ ማዕከል"
      description="Everything people asked a person for: hand-offs from the assistant, the contact form and reports. Answer here and the reply reaches them in the chat and their notification bell."
    >
      {summary.isLoading ? (
        <LoadingState label="Loading summary…" />
      ) : summary.error || !t ? (
        <ErrorState message={getErrorMessage(summary.error)} onRetry={() => summary.refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <StatTile label="New" value={t.new} hint="Not opened yet" tone={t.new ? "attention" : "default"} href="/admin/support?status=new" />
            <StatTile label="Open" value={t.open} hint="Being worked on" href="/admin/support?status=open" />
            <StatTile label="Waiting on customer" value={t.waiting_customer} hint="We replied last" href="/admin/support?status=waiting_customer" />
            <StatTile label="Overdue" value={t.overdue} hint="Past the first-response target" tone={t.overdue ? "attention" : "default"} />
            <StatTile label="Unassigned" value={t.unassigned} hint="Nobody owns these" tone={t.unassigned ? "attention" : "default"} href="/admin/support?assigned=none" />
            <StatTile label="Avg first response" value={formatMinutes(t.avg_first_response_minutes)} hint="Last 7 days" />
            <StatTile label="Resolved, 7 days" value={t.resolved_7d} />
          </div>
          <h2 className="text-muted-foreground mt-6 mb-2 text-[11px] font-medium tracking-wider uppercase">Related work in other queues</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
            <StatTile
              label="Hires awaiting a provider"
              value={s.related.hires_unmatched}
              hint="Staff must match these"
              href="/admin/marketplace/hires?status=open"
              tone={s.related.hires_unmatched ? "attention" : "default"}
            />
            <StatTile
              label="Deals to follow up"
              value={s.related.deals_to_follow_up}
              hint="Accepted, unpaid after 2 days: call both sides"
              href="/admin/marketplace/hires?follow_up=1"
              tone={s.related.deals_to_follow_up ? "attention" : "default"}
            />
            <StatTile
              label="Wrong-information reports"
              value={s.related.wrong_info_reports}
              hint="Open feedback flags"
              href="/admin/feedback"
              tone={s.related.wrong_info_reports ? "attention" : "default"}
            />
            <StatTile label="Provider applications" value={s.related.providers_pending} hint="Waiting for review" href="/admin/marketplace?status=pending" />
            <StatTile label="Service submissions" value={s.related.org_submissions_pending} hint="From organizations" href="/admin/submissions" />
          </div>
        </>
      )}

      <div className="mt-6 grid gap-4 lg:grid-cols-[13rem_1fr]">
        <nav aria-label="Queues" className="flex gap-1 overflow-x-auto text-xs lg:flex-col">
          {views.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => setParam({ ...v.params, page: null })}
              aria-current={activeView === v.key ? "true" : undefined}
              className={cn(
                "flex shrink-0 items-center justify-between gap-3 border-l-[3px] border-transparent px-2 py-1.5 text-left whitespace-nowrap hover:bg-muted",
                activeView === v.key && "border-primary bg-secondary text-primary font-semibold",
              )}
            >
              <span>{v.label}</span>
              <span className="flex items-center gap-1 tabular-nums">
                {!!v.overdue && <span className="bg-destructive/10 text-destructive rounded px-1 text-[10px] font-semibold">{v.overdue} late</span>}
                {v.count ?? ""}
              </span>
            </button>
          ))}
        </nav>

        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <label htmlFor="support-q" className="sr-only">
              Search
            </label>
            <Input
              id="support-q"
              className="h-8 w-64 text-xs"
              placeholder="Search ref, subject, name, phone, email"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <NativeSelect aria-label="Status" value={status} onChange={(e) => setParam({ status: e.target.value === "active" ? null : e.target.value, page: null })}>
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect aria-label="Priority" value={priority} onChange={(e) => setParam({ priority: e.target.value || null, page: null })}>
              <option value="">Any priority</option>
              {(Object.keys(PRIORITY_LABELS) as TicketPriority[]).map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABELS[p]}
                </option>
              ))}
            </NativeSelect>
            {tickets.isFetching && <span className="text-muted-foreground text-[11px]">Updating…</span>}
          </div>

          {tickets.isLoading ? (
            <LoadingState label="Loading requests…" />
          ) : tickets.error ? (
            <ErrorState message={getErrorMessage(tickets.error)} onRetry={() => tickets.refetch()} />
          ) : !tickets.payload?.items.length ? (
            <EmptyState title="Nothing here" description="No requests match this view. A clear queue is a good queue." />
          ) : (
            <div className="border-border overflow-x-auto border">
              <table className="w-full min-w-[56rem] text-xs">
                <thead className="bg-muted/50 text-muted-foreground text-left">
                  <tr>
                    <th className="px-3 py-2 font-medium">Ref</th>
                    <th className="px-3 py-2 font-medium">Request</th>
                    <th className="px-3 py-2 font-medium">Queue</th>
                    <th className="px-3 py-2 font-medium">Priority</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium">First response</th>
                    <th className="px-3 py-2 font-medium">Assignee</th>
                    <th className="px-3 py-2 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-border divide-y">
                  {tickets.payload.items.map((tk) => (
                    <tr
                      key={tk.id}
                      className={cn("hover:bg-muted/40 cursor-pointer", tk.overdue && "bg-destructive/5")}
                      onClick={() => router.push(`/admin/support/${tk.id}`)}
                    >
                      <td className="px-3 py-2.5 font-mono whitespace-nowrap">
                        <Link href={`/admin/support/${tk.id}`} className="text-primary hover:underline" onClick={(e) => e.stopPropagation()}>
                          {tk.ref}
                        </Link>
                      </td>
                      <td className="max-w-80 px-3 py-2.5">
                        <p className="flex items-center gap-1.5 font-medium">
                          {tk.awaiting_staff && <span className="bg-primary size-1.5 shrink-0 rounded-full" aria-label="Customer is waiting for us" />}
                          <span className="truncate">{tk.subject}</span>
                        </p>
                        <p className="text-muted-foreground truncate">
                          {tk.contact_name || tk.user_email || "Anonymous"}
                          {tk.last_message_preview ? ` · ${tk.last_message_preview}` : ""}
                        </p>
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">{tk.queue_label}</td>
                      <td className="px-3 py-2.5">
                        <PriorityBadge priority={tk.priority} />
                      </td>
                      <td className="px-3 py-2.5">
                        <TicketStatusBadge status={tk.status} label={tk.status_label} />
                      </td>
                      <td className="px-3 py-2.5">
                        {tk.first_response_at ? (
                          <span className="text-muted-foreground">Answered</span>
                        ) : (
                          <SlaBadge due={tk.sla_due_at} overdue={tk.overdue} done={tk.status === "resolved" || tk.status === "closed"} />
                        )}
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap">{tk.assignee_name ?? <span className="text-muted-foreground">Unassigned</span>}</td>
                      <td className="text-muted-foreground px-3 py-2.5 whitespace-nowrap">{timeAgo(tk.last_message_at ?? tk.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {pages > 1 && (
            <nav className="mt-3 flex items-center justify-between text-xs" aria-label="Pagination">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setParam({ page: page - 1 ? String(page - 1) : null })}>
                Previous
              </Button>
              <span className="text-muted-foreground">
                Page {page + 1} of {pages} · {tickets.payload?.total} requests
              </span>
              <Button variant="outline" size="sm" disabled={page + 1 >= pages} onClick={() => setParam({ page: String(page + 1) })}>
                Next
              </Button>
            </nav>
          )}
        </div>
      </div>
    </AdminPage>
  );
}
