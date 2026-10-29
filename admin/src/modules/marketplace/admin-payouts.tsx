"use client";

import { siteUrl } from "@cn/core/config/env";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { ADMIN_MONEY_PAGE_SIZE, formatETB, useAdminPayoutReview, useAdminPayouts, useDecidePayout } from "@cn/core/api/payments";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { StatTile } from "@/modules/shared/stat-tile";
import { EmptyState, ErrorState, LoadingState, formatDateTime } from "@cn/ui/guday/shared";
import { PayoutStatusBadge, bankLine } from "@cn/ui/marketplace/payout-status";
import type { AdminPayout, PaymentsMode, PayoutCheck, PayoutStatus } from "@cn/core/types/payments";

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
const CHAPA_TEST = "Chapa test mode: approving goes through Chapa's test system, no real money moves";

const CHECK_STYLE: Record<PayoutCheck["level"], string> = {
  block: "border-destructive/40 bg-destructive/5 text-destructive",
  warn: "border-gov-yellow/60 bg-gov-yellow/10 text-gov-ink",
  info: "border-border bg-muted/40 text-muted-foreground",
};
const CHECK_LABEL: Record<PayoutCheck["level"], string> = { block: "Stop", warn: "Check", info: "Note" };

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground text-[11px] tracking-wide uppercase">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

/** Who gets the money, whether the account is theirs, and which client payments it comes from. */
function PayoutReviewPanel({ p, onClose }: { p: AdminPayout; onClose: () => void }) {
  const { payload: r, isLoading, isError, error, refetch } = useAdminPayoutReview(p.id);
  const { decide, isPending } = useDecidePayout();
  const [mode, setMode] = useState<"idle" | "approve" | "reject">("idle");
  const [note, setNote] = useState("");
  const [failure, setFailure] = useState<string | null>(null);

  if (isLoading) return <LoadingState />;
  if (isError || !r) return <ErrorState message={error?.message ?? "Could not load this payout"} onRetry={() => refetch()} />;

  const blocks = r.checks.filter((c) => c.level === "block");
  const needsReason = blocks.length > 0;
  const send = async (decision: "approve" | "reject") => {
    setFailure(null);
    try {
      await decide(p.id, note.trim() ? { decision, note: note.trim() } : { decision });
      onClose();
    } catch (err) {
      setFailure(getErrorMessage(err, "Could not update this payout"));
    }
  };
  const pv = r.provider;
  const target = bankLine(p.bank_name, p.account_last4);

  return (
    <div className="mt-4 space-y-4 border-t pt-4">
      {r.checks.length > 0 && (
        <ul className="space-y-2" aria-label="Checks">
          {r.checks.map((c) => (
            <li key={c.code} className={cn("rounded-md border px-3 py-2 text-sm", CHECK_STYLE[c.level])}>
              <span className="font-semibold">{CHECK_LABEL[c.level]}: </span>
              {c.text}
            </li>
          ))}
        </ul>
      )}

      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 md:grid-cols-4">
        <Fact label="Name on national ID">
          {pv.verified_name ?? "Not verified"}
          {pv.national_id_verified && <span className="text-muted-foreground"> · verified{pv.id_verification_method === "fayda_sandbox" ? " (Fayda sandbox)" : ""}</span>}
        </Fact>
        <Fact label="Bank account holder">
          <span className={cn(blocks.some((b) => b.code === "name_mismatch") && "text-destructive font-semibold")}>{p.account_name ?? "-"}</span>
          <span className="text-muted-foreground"> · {target}</span>
        </Fact>
        <Fact label="TIN">{pv.has_tin ? "On file" : <span className="text-destructive">Missing</span>}</Fact>
        <Fact label="Licence">{pv.trade_license_no ?? "-"}</Fact>
        <Fact label="Provider since">{formatDateTime(pv.created_at)}</Fact>
        <Fact label="Account added">{formatDateTime(pv.payout_set_at)}</Fact>
        <Fact label="Paid out before">
          {r.history.paid_count ? `${r.history.paid_count} · ${formatETB(r.history.paid_total)}` : "Never"}
          {r.history.refused_count > 0 && <span className="text-muted-foreground"> · {r.history.refused_count} refused</span>}
        </Fact>
        <Fact label="Balance">
          {formatETB(r.balances.balance)}
          <span className="text-muted-foreground"> · {formatETB(r.balances.in_payout)} asked for</span>
        </Fact>
      </dl>

      <div>
        <h3 className="mb-2 text-sm font-semibold">What this pays for · earnings from client payments</h3>
        {r.earnings.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="text-muted-foreground text-left text-xs">
                <tr>
                  <th scope="col" className="py-1.5 font-medium">Date</th>
                  <th scope="col" className="py-1.5 font-medium">Job</th>
                  <th scope="col" className="py-1.5 font-medium">Client</th>
                  <th scope="col" className="py-1.5 text-right font-medium">Client paid</th>
                  <th scope="col" className="py-1.5 text-right font-medium">Provider share</th>
                  <th scope="col" className="py-1.5"><span className="sr-only">Statement</span></th>
                </tr>
              </thead>
              <tbody className="divide-border divide-y">
                {r.earnings.map((e, i) => (
                  <tr key={e.tx_ref ?? i}>
                    <td className="py-1.5 whitespace-nowrap">{formatDateTime(e.created_at)}</td>
                    <td className="py-1.5">{e.job_title ?? "-"}</td>
                    <td className="py-1.5">{e.client ?? "-"}</td>
                    <td className="py-1.5 text-right tabular-nums">
                      {e.client_paid != null ? formatETB(e.client_paid) : "-"}
                      {e.gateway && <span className="text-muted-foreground block text-[11px]">{e.gateway}</span>}
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{formatETB(e.amount)}</td>
                    <td className="py-1.5 text-right">
                      {e.tx_ref && (
                        <a href={siteUrl(`/receipts/statement/${encodeURIComponent(e.tx_ref)}`)} target="_blank" rel="noreferrer" className="text-primary text-xs hover:underline">
                          Statement
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-destructive text-sm">No earnings on record. Do not pay this out.</p>
        )}
      </div>

      {mode === "idle" && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={needsReason ? "outline" : "default"} onClick={() => setMode("approve")}>
            {needsReason ? "Approve anyway" : "Approve"}
          </Button>
          <Button size="sm" variant={needsReason ? "default" : "outline"} onClick={() => setMode("reject")}>Reject</Button>
          <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
        </div>
      )}
      {mode !== "idle" && (
        <form
          className="bg-secondary/50 space-y-2 rounded-md p-3 text-sm"
          onSubmit={(e) => {
            e.preventDefault();
            void send(mode);
          }}
        >
          <p>
            {mode === "approve" ? <>Send <strong>{formatETB(p.amount)}</strong> to {p.account_name} at {target}?</> : "Reject this payout? The money goes back to the provider's available balance."}
          </p>
          {(mode === "reject" || needsReason) && (
            <>
              <label htmlFor={`note-${p.id}`} className="block text-xs font-medium">
                {mode === "reject" ? "Reason, shown to the provider" : "Why approve despite the stop above? Kept on record (at least 10 characters)"}
              </label>
              <Input id={`note-${p.id}`} value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
            </>
          )}
          <div className="flex gap-2">
            <Button
              type="submit"
              size="sm"
              variant={mode === "reject" ? "destructive" : "default"}
              loading={isPending}
              disabled={mode === "reject" ? !note.trim() : needsReason && note.trim().length < 10}
            >
              {mode === "reject" ? "Reject payout" : "Send money"}
            </Button>
            <Button type="button" size="sm" variant="ghost" disabled={isPending} onClick={() => { setMode("idle"); setNote(""); }}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      {failure && <p className="text-destructive text-xs" role="alert">{failure}</p>}
    </div>
  );
}

function PayoutRow({ p }: { p: AdminPayout }) {
  const { decide, isPending } = useDecidePayout();
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const target = bankLine(p.bank_name, p.account_last4);

  const refresh = async () => {
    setError(null);
    setInfo(null);
    try {
      const result = await decide(p.id, { decision: "refresh" });
      if (result.status === "approved") setInfo("Still on its way. Check again later.");
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

      {p.status === "requested" && !reviewing && (
        <div className="mt-3">
          <Button size="sm" onClick={() => setReviewing(true)}>Review and decide</Button>
        </div>
      )}
      {reviewing && <PayoutReviewPanel p={p} onClose={() => setReviewing(false)} />}
      {p.status === "approved" && (
        <div className="mt-3">
          <Button size="sm" variant="outline" loading={isPending} onClick={refresh}>Check status</Button>
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
      {payload && (
        <p className="text-muted-foreground mb-3 text-xs">
          {payload.mode === "chapa" && payload.test_mode ? CHAPA_TEST : MODE_LABEL[payload.mode]}
        </p>
      )}
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
