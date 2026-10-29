"use client";

import { siteUrl } from "@cn/core/config/env";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { ADMIN_MONEY_PAGE_SIZE, formatETB, useAdminPayouts, useDecidePayout } from "@cn/core/api/payments";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { StatTile } from "@/modules/shared/stat-tile";
import { EmptyState, ErrorState, LoadingState, formatDateTime } from "@cn/ui/guday/shared";
import { PayoutStatusBadge, bankLine } from "@cn/ui/marketplace/payout-status";
import type { AdminPayout, PaymentsMode, PayoutStatus } from "@cn/core/types/payments";

const FILTERS: { value: PayoutStatus; label: string; empty: string }[] = [
  { value: "requested", label: "Waiting", empty: "No withdrawals are waiting for approval." },
  { value: "approved", label: "Processing", empty: "No payouts are being processed." },
  { value: "paid", label: "Paid", empty: "No payouts have been paid yet." },
  { value: "rejected", label: "Rejected", empty: "No payouts were rejected." },
  { value: "failed", label: "Failed", empty: "No payouts failed." },
];

const MODE_LABEL: Record<PaymentsMode, string> = {
  off: "Online payments are off",
  simulated: "Test mode: approving marks the payout paid at once, no real money moves",
  chapa: "Live with Chapa: approving sends a bank transfer; press Check status to see when it lands",
};

function PayoutRow({ p }: { p: AdminPayout }) {
  const { decide, isPending } = useDecidePayout();
  const [mode, setMode] = useState<"idle" | "approve" | "reject">("idle");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const target = bankLine(p.bank_name, p.account_last4);

  const send = async (decision: "approve" | "reject" | "refresh") => {
    setError(null);
    setInfo(null);
    try {
      const result = await decide(p.id, decision === "reject" ? { decision, note: note.trim() } : { decision });
      setMode("idle");
      setNote("");
      if (decision === "refresh" && result.status === "approved") setInfo("Still on its way. Check again later.");
    } catch (err) {
      setError(getErrorMessage(err, "Could not update this payout"));
    }
  };

  return (
    <li className="border-border bg-card rounded-xl border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-sm">
            {p.provider_slug ? (
              <a href={siteUrl(`/providers/${p.provider_slug}`)} target="_blank" rel="noreferrer" className="text-primary font-medium hover:underline">{p.provider_name}</a>
            ) : (
              <span className="font-medium">{p.provider_name}</span>
            )}
            <span className="text-muted-foreground"> to </span>
            {target}
            {p.account_name && <span className="text-muted-foreground"> ({p.account_name})</span>}
          </p>
          <p className="text-muted-foreground text-xs">
            Requested {formatDateTime(p.created_at)}
            {p.reference && <> · <span className="font-mono">{p.reference}</span></>}
            {p.gateway_reference && <> · bank ref <span className="font-mono">{p.gateway_reference}</span></>}
          </p>
          {p.decided_at && (
            <p className="text-muted-foreground text-xs">
              {p.status === "rejected" ? "Rejected" : "Approved"}
              {p.decided_by ? ` by ${p.decided_by}` : ""} {formatDateTime(p.decided_at)}
              {p.paid_at ? ` · paid ${formatDateTime(p.paid_at)}` : ""}
            </p>
          )}
          {p.note && <p className="text-xs">Note: {p.note}</p>}
        </div>
        <div className="flex items-center gap-3">
          <p className="text-lg font-semibold tabular-nums">{formatETB(p.amount)}</p>
          <PayoutStatusBadge status={p.status} />
        </div>
      </div>

      {p.status === "requested" && mode === "idle" && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" onClick={() => setMode("approve")}>Approve</Button>
          <Button size="sm" variant="outline" onClick={() => setMode("reject")}>Reject</Button>
        </div>
      )}
      {p.status === "requested" && mode === "approve" && (
        <div className="bg-secondary/50 mt-3 flex flex-wrap items-center gap-2 rounded-md p-3 text-sm">
          <span>Send {formatETB(p.amount)} to {target}?</span>
          <Button size="sm" loading={isPending} onClick={() => send("approve")}>Send money</Button>
          <Button size="sm" variant="ghost" disabled={isPending} onClick={() => setMode("idle")}>Cancel</Button>
        </div>
      )}
      {p.status === "requested" && mode === "reject" && (
        <form
          className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center"
          onSubmit={(e) => {
            e.preventDefault();
            if (note.trim()) void send("reject");
          }}
        >
          <label htmlFor={`reject-${p.id}`} className="sr-only">Reason for rejecting, shown to the provider</label>
          <Input
            id={`reject-${p.id}`}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Reason, shown to the provider"
            className="sm:flex-1"
            autoFocus
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" variant="destructive" disabled={!note.trim()} loading={isPending}>Reject payout</Button>
            <Button type="button" size="sm" variant="ghost" disabled={isPending} onClick={() => setMode("idle")}>Cancel</Button>
          </div>
        </form>
      )}
      {p.status === "approved" && (
        <div className="mt-3">
          <Button size="sm" variant="outline" loading={isPending} onClick={() => send("refresh")}>Check status</Button>
        </div>
      )}
      {error && <p className="text-destructive mt-2 text-xs" role="alert">{error}</p>}
      {info && <p className="text-muted-foreground mt-2 text-xs" role="status">{info}</p>}
    </li>
  );
}

export function AdminPayouts() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const raw = params.get("status");
  const filter = FILTERS.find((f) => f.value === raw) ?? FILTERS[0];
  const setStatus = (v: PayoutStatus) => {
    const next = new URLSearchParams(params.toString());
    if (v === "requested") next.delete("status");
    else next.set("status", v);
    next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const [page, setPage] = useUrlPage();
  const { payload, isLoading, isError, error, refetch } = useAdminPayouts(filter.value, page);
  const totals = payload?.totals;
  const items = payload?.items ?? [];

  return (
    <AdminPage
      title="Payouts · ክፍያ ማስተላለፍ"
      description="Withdrawals providers asked for from their earnings. Approving sends the money to the provider's bank account."
    >
      {payload && <p className="text-muted-foreground mb-3 text-xs">{MODE_LABEL[payload.mode]}</p>}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Waiting for approval"
          value={totals ? totals.requested : "…"}
          hint={totals ? formatETB(totals.requested_amount) : undefined}
          href="?status=requested"
          tone={totals?.requested ? "attention" : "default"}
        />
        <StatTile label="Processing" value={totals ? totals.processing : "…"} hint="Approved, transfer not confirmed" href="?status=approved" />
        <StatTile label="Paid out in total" value={totals ? formatETB(totals.paid_amount) : "…"} href="?status=paid" />
        <StatTile label="Owed to providers" value={totals ? formatETB(totals.owed_to_providers) : "…"} hint="Earned and not yet paid out" />
      </div>

      <div role="group" aria-label="Filter by status" className="mb-3 flex flex-wrap gap-2 text-xs">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            aria-pressed={filter.value === f.value}
            onClick={() => setStatus(f.value)}
            className={cn("rounded-full border px-3 py-1", filter.value === f.value ? "border-primary bg-secondary text-primary font-medium" : "border-border")}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load payouts"} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title={filter.empty} />
      ) : (
        <ul className="space-y-3">
          {items.map((p) => (
            <PayoutRow key={p.id} p={p} />
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={ADMIN_MONEY_PAGE_SIZE} total={payload?.total ?? 0} onPage={setPage} />
    </AdminPage>
  );
}
