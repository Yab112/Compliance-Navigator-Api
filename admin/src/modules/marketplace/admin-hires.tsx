"use client";

import { siteUrl } from "@cn/core/config/env";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  ADMIN_MARKET_PAGE_SIZE,
  useAdminHires,
  useAdminProviders,
  useAdminReviewChanges,
  useAdminReviews,
  useMarketAction,
  type ReviewChangeStatus,
} from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { EmptyState, ErrorState, LoadingState, NativeSelect, formatDate, formatDateTime } from "@cn/ui/guday/shared";
import { PriceLine } from "@cn/ui/marketplace/payment-badge";
import { HireStatusBadge, Stars } from "@cn/ui/marketplace/trust";
import { HIRE_STATUS } from "@cn/ui/marketplace/constants";
import type { AdminReview, Hire, HireStatus, ReviewChange } from "@cn/core/types/provider";

function AssignProvider({ hire }: { hire: Hire }) {
  const { data } = useAdminProviders({ status: "approved", limit: 200 });
  const { run, isPending } = useMarketAction<{ provider_id: string }>();
  const [pick, setPick] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <NativeSelect aria-label="Assign provider" className="w-64" value={pick} onChange={(e) => setPick(e.target.value)}>
        <option value="">Choose an approved provider</option>
        {(data?.payload.items ?? []).map((p) => (
          <option key={p.id} value={p.id}>{p.display_name} · score {p.trust_score}</option>
        ))}
      </NativeSelect>
      <Button size="sm" disabled={!pick} loading={isPending}
        onClick={async () => {
          setError(null);
          try {
            await run(apiPaths.admin.marketHire(hire.id), MTD.PATCH, { provider_id: pick });
          } catch (err) {
            setError(getErrorMessage(err));
          }
        }}>
        Assign
      </Button>
      {error && <span className="text-destructive text-xs">{error}</span>}
    </div>
  );
}

function DisputeDecision({ hire }: { hire: Hire }) {
  const { run, isPending } = useMarketAction<{ decision: string; note?: string }>();
  const [note, setNote] = useState("");
  return (
    <div className="mt-2 space-y-2 border border-amber-300 bg-amber-50 p-3 text-xs">
      <p><strong>Complaint:</strong> {hire.dispute_reason}</p>
      <Input placeholder="Finding (shown to the client)" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="flex gap-2">
        <Button size="sm" variant="destructive" loading={isPending}
          onClick={() => run(apiPaths.admin.marketDispute(hire.id), MTD.POST, { decision: "upheld", note: note.trim() || undefined })}>
          Uphold (minus 10 trust points)
        </Button>
        <Button size="sm" variant="outline" loading={isPending}
          onClick={() => run(apiPaths.admin.marketDispute(hire.id), MTD.POST, { decision: "dismissed", note: note.trim() || undefined })}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}

export function AdminHires() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const status = (params.get("status") ?? "") as HireStatus | "";
  const disputed = params.get("disputed") === "1";
  const followUp = params.get("follow_up") === "1";
  const [page, setPage] = useUrlPage();
  // A filter change starts again at page 1
  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(params.toString());
    if (v) next.set(k, v);
    else next.delete(k);
    next.delete("page");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };
  const { data, isLoading, isError, error, refetch } = useAdminHires({
    status: status || undefined,
    disputed: disputed || undefined,
    follow_up: followUp || undefined,
    limit: ADMIN_MARKET_PAGE_SIZE,
    offset: page * ADMIN_MARKET_PAGE_SIZE,
  });
  const items = data?.payload.items ?? [];
  const total = data?.payload.total ?? 0;

  return (
    <AdminPage title="Hires and complaints · ቅጥሮች" description="Every request a client sent to a provider. Assign open requests and decide complaints.">
      <div className="mb-4 flex flex-wrap gap-2 text-xs">
        <NativeSelect aria-label="Status" className="w-56" value={status} onChange={(e) => set("status", e.target.value || null)}>
          <option value="">All statuses</option>
          {(Object.keys(HIRE_STATUS) as HireStatus[]).map((s) => (
            <option key={s} value={s}>{HIRE_STATUS[s].label}</option>
          ))}
        </NativeSelect>
        <label className="flex items-center gap-2">
          <input type="checkbox" className="accent-primary" checked={disputed} onChange={(e) => set("disputed", e.target.checked ? "1" : null)} />
          With complaints only
        </label>
        <label className="flex items-center gap-2" title="Accepted more than 48 hours ago and still not paid">
          <input type="checkbox" className="accent-primary" checked={followUp} onChange={(e) => set("follow_up", e.target.checked ? "1" : null)} />
          Deals to follow up (unpaid after 2 days)
        </label>
      </div>
      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load hires"} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title="Nothing here" />
      ) : (
        <>
          <p className="text-muted-foreground mb-2 text-xs">{total} hire{total === 1 ? "" : "s"}</p>
          <ul className="space-y-2">
            {items.map((h) => (
              <li key={h.id} className={cn("border-border bg-card border p-3 text-xs", h.disputed && h.dispute_status === "open" && "border-amber-400")}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-medium">{h.title}</span>
                  <HireStatusBadge status={h.status} />
                </div>
                <p className="text-muted-foreground mt-1">
                  Client {h.client_name} ({h.client_phone}{h.client_telegram ? `, Telegram @${h.client_telegram}` : ""}) ·{" "}
                  {h.provider_name ? <Link href={`/marketplace/${h.provider_id}`} className="text-primary underline">{h.provider_name}</Link> : "no provider yet"} ·{" "}
                  {formatDateTime(h.created_at)}
                  {h.review_rating ? <> · reviewed <Stars value={h.review_rating} /></> : null}
                </p>
                {h.details && <p className="mt-1">{h.details}</p>}
                {h.agreed_price != null && <div className="mt-1"><PriceLine price={h.agreed_price} note={h.price_note} status={h.payment_status} /></div>}
                {h.admin_note && <p className="text-muted-foreground mt-1">Staff note: {h.admin_note}</p>}
                {h.status === "open" && <AssignProvider hire={h} />}
                {h.disputed && h.dispute_status === "open" && <DisputeDecision hire={h} />}
                {h.disputed && h.dispute_status !== "open" && (
                  <p className="mt-1">Complaint {h.dispute_status}{h.dispute_note ? `: ${h.dispute_note}` : ""}</p>
                )}
              </li>
            ))}
          </ul>
          <Pager page={page} pageSize={ADMIN_MARKET_PAGE_SIZE} total={total} onPage={setPage} />
        </>
      )}
    </AdminPage>
  );
}

function ChangeSide({ label, rating, comment }: { label: string; rating: number; comment?: string | null }) {
  return (
    <div className="border-border min-w-0 rounded border p-2">
      <p className="text-muted-foreground text-[10px] font-semibold tracking-wide uppercase">{label}</p>
      <Stars value={rating} />
      <p className={cn("mt-1 text-sm whitespace-pre-line", !comment && "text-muted-foreground italic")}>{comment || "No comment"}</p>
    </div>
  );
}

function ReviewChangeItem({ change: c }: { change: ReviewChange }) {
  const { run, isPending } = useMarketAction<{ decision: "approve" | "reject"; note?: string }>();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const decide = async (decision: "approve" | "reject") => {
    setError(null);
    try {
      await run(apiPaths.admin.reviewChange(c.id), MTD.POST, { decision, note: note.trim() || undefined });
    } catch (err) {
      setError(getErrorMessage(err, "Could not save the decision"));
    }
  };
  return (
    <li className={cn("border-border bg-card border p-3 text-xs", c.status === "pending" && "border-amber-400")}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium">{c.job_title}</span>
        <span className="text-muted-foreground">requested {formatDateTime(c.created_at)}</span>
      </div>
      <p className="text-muted-foreground mt-1">
        Client {c.client_name} · provider{" "}
        <a href={siteUrl(`/providers/${c.provider_slug}`)} target="_blank" rel="noreferrer" className="text-primary underline">{c.provider_name}</a>
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <ChangeSide label="Current review" rating={c.old_rating} comment={c.old_comment} />
        <ChangeSide label="Requested change" rating={c.new_rating} comment={c.new_comment} />
      </div>
      <p className="mt-2"><strong>Client&apos;s reason:</strong> {c.reason}</p>
      {c.status === "pending" ? (
        <div className="mt-2 space-y-2">
          <Input aria-label="Note to the client (optional)" placeholder="Note to the client (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex gap-2">
            <Button size="sm" loading={isPending} onClick={() => decide("approve")}>Approve</Button>
            <Button size="sm" variant="outline" loading={isPending} onClick={() => decide("reject")}>Reject</Button>
          </div>
          {error && <p className="text-destructive">{error}</p>}
        </div>
      ) : (
        <p className="mt-2">
          <span className={cn("font-medium", c.status === "approved" ? "text-emerald-800" : "text-amber-800")}>
            {c.status === "approved" ? "Approved" : "Rejected"}
          </span>
          {c.decided_by ? ` by ${c.decided_by}` : ""}
          {c.decided_at ? ` on ${formatDate(c.decided_at)}` : ""}
          {c.decision_note ? `: ${c.decision_note}` : ""}
        </p>
      )}
    </li>
  );
}

const CHANGE_STATUSES: { key: ReviewChangeStatus; label: string }[] = [
  { key: "pending", label: "Waiting" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
];

function ReviewChanges({
  status,
  onStatus,
  page,
  onPage,
}: {
  status: ReviewChangeStatus;
  onStatus: (s: ReviewChangeStatus) => void;
  page: number;
  onPage: (page: number) => void;
}) {
  const { data, isLoading, isError, error, refetch } = useAdminReviewChanges(status, page);
  const items = data?.payload.items ?? [];
  return (
    <>
      <p className="text-muted-foreground mb-3 text-xs">
        Clients can&apos;t edit a published review. They ask for a change, and it only appears once approved. Approving replaces the
        rating and comment; rejecting keeps the review as it is.
      </p>
      <NativeSelect aria-label="Change request status" className="mb-3 w-48 text-xs" value={status} onChange={(e) => onStatus(e.target.value as ReviewChangeStatus)}>
        {CHANGE_STATUSES.map((s) => (
          <option key={s.key} value={s.key}>{s.label}</option>
        ))}
      </NativeSelect>
      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load change requests"} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title={status === "pending" ? "No change requests waiting" : `No ${status} change requests`} />
      ) : (
        <ul className="space-y-2">
          {items.map((c) => (
            <ReviewChangeItem key={c.id} change={c} />
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={ADMIN_MARKET_PAGE_SIZE} total={data?.payload.total ?? 0} onPage={onPage} />
    </>
  );
}

type ReviewTab = "all" | "low" | "hidden" | "changes";
const REVIEW_TABS: { key: ReviewTab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "low", label: "1 to 2 stars" },
  { key: "hidden", label: "Hidden" },
  { key: "changes", label: "Change requests" },
];

export function AdminReviews() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tabParam = params.get("tab");
  const filter: ReviewTab = REVIEW_TABS.some((t) => t.key === tabParam) ? (tabParam as ReviewTab) : "all";
  const statusParam = params.get("status");
  const changeStatus: ReviewChangeStatus = CHANGE_STATUSES.some((s) => s.key === statusParam) ? (statusParam as ReviewChangeStatus) : "pending";
  const [page, setPage] = useUrlPage();
  // Every tab or status change starts again at page 1
  const setParams = (next: Record<string, string | null>) => {
    const q = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v) q.set(k, v);
      else q.delete(k);
    }
    q.delete("page");
    const qs = q.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const setFilter = (f: ReviewTab) => setParams({ tab: f === "all" ? null : f, status: null });
  const { data, isLoading, isError, error, refetch } = useAdminReviews({
    hidden: filter === "hidden" ? true : undefined,
    max_rating: filter === "low" ? 2 : undefined,
    offset: page * ADMIN_MARKET_PAGE_SIZE,
  }, filter !== "changes");
  const pendingChanges = useAdminReviewChanges("pending").data?.payload.pending ?? 0;
  const { run, isPending } = useMarketAction<{ hidden: boolean; reason?: string }>();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const items: AdminReview[] = data?.payload.items ?? [];

  return (
    <AdminPage title="Review moderation · ግምገማዎች" description="Hide reviews that are abusive, contain personal data or are not about the job. Hidden reviews stop counting towards the score and stay in the audit log.">
      <div className="mb-4 flex flex-wrap gap-2 text-xs" role="tablist" aria-label="Reviews">
        {REVIEW_TABS.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={filter === t.key} onClick={() => setFilter(t.key)}
            className={cn("rounded-full border px-3 py-1", filter === t.key ? "border-primary bg-secondary text-primary font-medium" : "border-border")}>
            {t.label}
            {t.key === "changes" && pendingChanges > 0 && (
              <span className="ml-1.5 rounded-full bg-amber-500 px-1.5 text-[10px] font-semibold text-white" aria-label={`${pendingChanges} waiting`}>
                {pendingChanges}
              </span>
            )}
          </button>
        ))}
      </div>
      {filter === "changes" ? (
        <ReviewChanges
          status={changeStatus}
          onStatus={(s) => setParams({ status: s === "pending" ? null : s })}
          page={page}
          onPage={setPage}
        />
      ) : isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load reviews"} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title="No reviews" />
      ) : (
        <ul className="space-y-2">
          {items.map((r) => (
            <li key={r.id} className={cn("border-border bg-card border p-3 text-xs", r.hidden && "opacity-70")}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="flex items-center gap-2">
                  <Stars value={r.rating} />
                  <a href={siteUrl(`/providers/${r.provider_slug}`)} target="_blank" rel="noreferrer" className="font-medium hover:underline">{r.provider_name}</a>
                  <span className="text-muted-foreground">· {r.job_title}</span>
                </span>
                <span className="text-muted-foreground">{r.client_email} · {formatDate(r.created_at)}</span>
              </div>
              {r.comment && <p className="mt-1 text-sm">{r.comment}</p>}
              {r.hidden ? (
                <p className="mt-2 text-amber-800">
                  Hidden by {r.hidden_by}: {r.hidden_reason}{" "}
                  <button type="button" className="text-primary underline" disabled={isPending}
                    onClick={() => run(apiPaths.admin.marketModerate(r.id), MTD.POST, { hidden: false })}>Restore</button>
                </p>
              ) : (
                <div className="mt-2 flex gap-2">
                  <Input placeholder="Reason to hide" value={reasons[r.id] ?? ""} onChange={(e) => setReasons((x) => ({ ...x, [r.id]: e.target.value }))} />
                  <Button size="sm" variant="outline" disabled={(reasons[r.id] ?? "").trim().length < 3} loading={isPending}
                    onClick={() => run(apiPaths.admin.marketModerate(r.id), MTD.POST, { hidden: true, reason: reasons[r.id].trim() })}>
                    Hide
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {filter !== "changes" && (
        <Pager page={page} pageSize={ADMIN_MARKET_PAGE_SIZE} total={data?.payload.total ?? 0} onPage={setPage} />
      )}
    </AdminPage>
  );
}
