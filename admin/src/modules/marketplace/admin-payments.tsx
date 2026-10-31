"use client";

import { siteUrl } from "@cn/core/config/env";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  ADMIN_MONEY_PAGE_SIZE,
  formatBirr,
  formatETB,
  useAdminPayments,
  useAdminRefunds,
  usePaymentsExport,
  useRefundAction,
  useVerifyPayment,
} from "@cn/core/api/payments";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Badge } from "@cn/ui/badge";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { useCan } from "@/modules/access/api";
import { STAT_STRIP, StatTile } from "@/modules/shared/stat-tile";
import { EmptyState, LoadingState, formatDateTime } from "@cn/ui/guday/shared";
import { ErrorState } from "@/modules/shared/states";
import type { AdminPayment, AdminPaymentFilters, PaymentStatus, PaymentsMode, Refund, RefundStatus } from "@cn/core/types/payments";
import { RefundForm } from "./refund-dialog";

const STATUS: Record<PaymentStatus, { label: string; className: string }> = {
  success: { label: "Paid", className: "bg-emerald-100 text-emerald-900" },
  pending: { label: "Pending", className: "bg-amber-100 text-amber-900" },
  failed: { label: "Failed", className: "bg-red-100 text-red-900" },
  cancelled: { label: "Cancelled", className: "bg-zinc-200 text-zinc-700" },
};

const FILTERS: { value: PaymentStatus | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "success", label: "Paid" },
  { value: "pending", label: "Pending" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

const MODE_LABEL: Record<PaymentsMode, string> = {
  off: "Online payments are off",
  simulated: "Test mode (simulated gateway, no real money)",
  chapa: "Live with Chapa",
};

const REFUND_STATUS: Record<RefundStatus, { label: string; className: string }> = {
  sending: { label: "Sending", className: "bg-amber-100 text-amber-900" },
  processing: { label: "With Chapa", className: "bg-amber-100 text-amber-900" },
  refunded: { label: "Refunded", className: "bg-emerald-100 text-emerald-900" },
  manual_pending: { label: "To send by bank", className: "bg-amber-100 text-amber-900" },
  needs_check: { label: "Needs checking", className: "bg-red-100 text-red-900" },
  failed: { label: "Failed", className: "bg-zinc-200 text-zinc-700" },
};

const UNAPPLIED: Record<string, string> = {
  duplicate: "Extra payment: the job was already paid. Not credited; refund it.",
  job_closed: "Paid after the job was cancelled. Not credited; refund it.",
};

const birr = (n: number) => `${formatBirr(n)} ETB`;

/** One refund with the step staff take next: ask Chapa, confirm the bank transfer, or mark it failed. */

/** approved_by is stored as "maker (approved by checker)"; show only the part after the maker. */
function approvalNote(requestedBy: string | null | undefined, approvedBy: string | null | undefined): string | null {
  if (!approvedBy) return null;
  const inner = approvedBy.match(/\(([^()]+)\)$/)?.[1];
  if (inner) return inner;
  return approvedBy === requestedBy ? null : `approved by ${approvedBy}`;
}

function RefundRow({ r, canRefund }: { r: Refund; canRefund: boolean }) {
  const { act, isPending } = useRefundAction();
  const [mode, setMode] = useState<"idle" | "confirm" | "mark_failed">("idle");
  const [note, setNote] = useState("");
  const [ref, setRef] = useState("");
  const [msg, setMsg] = useState<{ error: boolean; text: string } | null>(null);
  const run = async (action: "refresh" | "confirm" | "mark_failed") => {
    setMsg(null);
    try {
      const after = await act(r.id, { action, note: note.trim() || undefined, transfer_reference: ref.trim() || undefined });
      if (action === "refresh" && after.status === r.status) setMsg({ error: false, text: "No change yet. Check again later." });
      setMode("idle");
    } catch (err) {
      setMsg({ error: true, text: getErrorMessage(err, "Could not update this refund") });
    }
  };
  const st = REFUND_STATUS[r.status];
  return (
    <li className="border-border border-t py-2 text-xs first:border-t-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono">{r.reference}</span>
        <Badge className={st.className}>{st.label}</Badge>
        <span className="font-medium tabular-nums">{formatETB(r.amount)}</span>
        <span className="text-muted-foreground">
          · from provider {formatETB(r.provider_amount)} · commission {formatETB(r.commission + r.commission_vat)}
        </span>
      </div>
      <p className="text-muted-foreground">
        {formatDateTime(r.created_at)} · asked by {r.requested_by ?? "?"}
        {approvalNote(r.requested_by, r.approved_by) && <> · {approvalNote(r.requested_by, r.approved_by)}</>}
        {r.method === "manual" && r.client_bank_name && <> · to {r.client_bank_name} ({r.client_account_name}) ••••{r.client_account_last4}</>}
      </p>
      <p>Reason: {r.reason}</p>
      {r.error && <p className="text-destructive">Gateway said: {r.error}</p>}
      {r.transfer_reference && <p>Bank transfer reference: <span className="font-mono">{r.transfer_reference}</span></p>}
      {r.status === "manual_pending" && r.client_account_number && (
        <p>
          Send to account number <span className="font-mono select-all">{r.client_account_number}</span>, then confirm with the bank reference.
        </p>
      )}
      {r.status === "refunded" && (
        <a href={siteUrl(`/receipts/refund/${r.id}`)} target="_blank" rel="noreferrer" className="text-primary hover:underline">Refund receipt</a>
      )}
      {canRefund && ["processing", "needs_check", "manual_pending"].includes(r.status) && mode === "idle" && (
        <div className="mt-1 flex flex-wrap gap-2">
          {r.gateway_ref && (r.status === "processing" || r.status === "needs_check") && (
            <Button size="sm" variant="outline" loading={isPending} onClick={() => run("refresh")}>Check with Chapa</Button>
          )}
          {(r.status === "manual_pending" || r.status === "needs_check") && (
            <>
              <Button size="sm" variant="outline" onClick={() => setMode("confirm")}>{r.status === "manual_pending" ? "Confirm sent" : "It went through"}</Button>
              <Button size="sm" variant="ghost" onClick={() => setMode("mark_failed")}>Mark failed</Button>
            </>
          )}
        </div>
      )}
      {mode !== "idle" && (
        <form
          className="bg-secondary/50 mt-2 space-y-2 rounded-md p-2"
          onSubmit={(e) => {
            e.preventDefault();
            void run(mode);
          }}
        >
          {mode === "confirm" && r.status === "manual_pending" && (
            <div>
              <label htmlFor={`ref-${r.id}`} className="block font-medium">Bank transfer reference</label>
              <Input id={`ref-${r.id}`} value={ref} onChange={(e) => setRef(e.target.value)} autoFocus />
            </div>
          )}
          <div>
            <label htmlFor={`note-${r.id}`} className="block font-medium">
              {mode === "mark_failed" ? "What you checked (at least 10 characters). The provider's share is given back and the hire is flagged again." : "What you checked"}
            </label>
            <Input id={`note-${r.id}`} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="flex gap-2">
            <Button type="submit" size="sm" variant={mode === "mark_failed" ? "destructive" : "default"} loading={isPending}
              disabled={mode === "mark_failed" ? note.trim().length < 10 : r.status === "manual_pending" ? ref.trim().length < 3 : note.trim().length < 5}>
              {mode === "mark_failed" ? "Mark failed" : "Confirm"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setMode("idle")}>Cancel</Button>
          </div>
        </form>
      )}
      {msg && <p className={msg.error ? "text-destructive" : "text-muted-foreground"} role={msg.error ? "alert" : "status"}>{msg.text}</p>}
    </li>
  );
}

function PaymentRefunds({ txRef, canRefund }: { txRef: string; canRefund: boolean }) {
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(ADMIN_MONEY_PAGE_SIZE);
  const { payload, isLoading, isError, error } = useAdminRefunds({ tx_ref: txRef }, page, true, size);
  if (isLoading) return <LoadingState />;
  if (isError) return <p className="text-destructive text-xs" role="alert">{error?.message ?? "Could not load refunds"}</p>;
  if (!payload?.items.length) return <p className="text-muted-foreground text-xs">No refunds for this payment.</p>;
  return (
    <div>
      <ul>{payload.items.map((r) => <RefundRow key={r.id} r={r} canRefund={canRefund} />)}</ul>
      <Pager page={page} pageSize={size} total={payload.total} onPage={setPage} onPageSize={(n) => { setSize(n); setPage(0); }} />
    </div>
  );
}

/** Staff actions on one payment: re-check a pending one with Chapa, refund a paid one, see its refunds. */
function PaymentActions({ p, canRefund }: { p: AdminPayment; canRefund: boolean }) {
  const { verify, isPending } = useVerifyPayment();
  const [open, setOpen] = useState<"none" | "refund" | "refunds">("none");
  const [msg, setMsg] = useState<{ error: boolean; text: string } | null>(null);
  const check = async () => {
    setMsg(null);
    try {
      const res = await verify(p.tx_ref);
      setMsg({ error: false, text: res.changed ? `Chapa says: ${STATUS[res.payment.status]?.label ?? res.payment.status}. Recorded.` : "Still pending with the payment service." });
    } catch (err) {
      setMsg({ error: true, text: getErrorMessage(err, "Could not check this payment") });
    }
  };
  const canStartRefund = canRefund && p.status === "success" && p.refundable > 0;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {p.status === "pending" && <Button size="sm" variant="outline" loading={isPending} onClick={check}>Check with Chapa</Button>}
        {canStartRefund && open !== "refund" && (
          <Button size="sm" variant={p.refund_needed || p.unapplied_reason ? "destructive" : "outline"} onClick={() => setOpen("refund")}>Refund</Button>
        )}
        {(p.refunded_amount > 0 || p.refunds_open > 0) && (
          <Button size="sm" variant="ghost" aria-expanded={open === "refunds"} onClick={() => setOpen(open === "refunds" ? "none" : "refunds")}>
            Refunds{p.refunds_open ? ` (${p.refunds_open} open)` : ""}
          </Button>
        )}
      </div>
      {open === "refund" && <RefundForm payment={p} onClose={() => setOpen("none")} />}
      {open === "refunds" && <PaymentRefunds txRef={p.tx_ref} canRefund={canRefund} />}
      {msg && <p className={cn("text-xs", msg.error ? "text-destructive" : "text-muted-foreground")} role={msg.error ? "alert" : "status"}>{msg.text}</p>}
    </div>
  );
}

function PaymentCard({ p, canRefund }: { p: AdminPayment; canRefund: boolean }) {
  return (
    <li className={cn("border-border bg-card border p-3 text-xs", (p.refund_needed || p.unapplied_reason) && p.refundable > 0 && "border-destructive/50")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm">
            <Link href={`/marketplace/hires/${p.engagement_id}`} className="text-primary font-medium hover:underline">{p.title}</Link>
            {p.is_test && <span className="bg-muted ml-2 rounded px-1.5 text-[10px]">Test</span>}
            {p.refund_needed && p.refundable > 0 && <span className="bg-destructive/10 text-destructive ml-2 rounded px-1.5 text-[10px] font-medium">Refund needed</span>}
          </p>
          <p className="text-muted-foreground">
            {p.status === "success" ? `${p.client_name} paid` : p.status === "pending" ? `${p.client_name} is paying` : `Payment from ${p.client_name} to`}{" "}
            {p.provider_slug ? (
              <a href={siteUrl(`/providers/${p.provider_slug}`)} target="_blank" rel="noreferrer" className="text-primary hover:underline">{p.provider_name}</a>
            ) : (
              p.provider_name
            )}
            {p.status === "failed" ? " failed" : p.status === "cancelled" ? " was cancelled" : ""}{" "}
            · {formatDateTime(p.created_at)}
            {p.verified_at && <> · verified {formatDateTime(p.verified_at)}</>}
          </p>
          <p className="text-muted-foreground font-mono text-[11px] break-all">
            {p.tx_ref} · {p.gateway}
            {p.gateway_reference ? ` · ${p.gateway_reference}` : ""}
            {p.payment_method ? ` · ${p.payment_method}` : ""}
          </p>
          {p.unapplied_reason && <p className="text-destructive">{UNAPPLIED[p.unapplied_reason]}</p>}
        </div>
        <div className="text-right">
          <p className="text-base font-semibold tabular-nums">{formatBirr(p.amount)} {p.currency}</p>
          <Badge className={STATUS[p.status]?.className}>{STATUS[p.status]?.label ?? p.status}</Badge>
          {p.refunded_amount > 0 && <p className="text-destructive tabular-nums">refunded {birr(p.refunded_amount)}</p>}
        </div>
      </div>
      {p.status === "success" && (
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3 lg:grid-cols-6">
          {[
            ["Price", p.price],
            ["Provider VAT", p.provider_vat],
            ["Commission", p.commission_amount],
            ["VAT on commission", p.commission_vat],
            ["To provider", p.provider_amount],
            ["Chapa fee", p.gateway_fee],
          ].map(([label, value]) => (
            <div key={label as string}>
              <dt className="text-muted-foreground text-[11px]">{label}</dt>
              <dd className="tabular-nums">{value == null ? "-" : formatBirr(value as number)}</dd>
            </div>
          ))}
        </dl>
      )}
      <div className="mt-2">
        <PaymentActions p={p} canRefund={canRefund} />
      </div>
    </li>
  );
}

export function AdminPayments() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { can } = useCan();
  const exportCsv = usePaymentsExport();
  const raw = params.get("status") ?? "";
  const status = (FILTERS.some((f) => f.value === raw) ? raw : "") as PaymentStatus | "";
  const q = params.get("q") ?? "";
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const needsRefund = params.get("refund") === "1";
  const engagement = params.get("engagement") ?? "";
  const [search, setSearch] = useState(q);
  const [shownQ, setShownQ] = useState(q);
  const [exportError, setExportError] = useState<string | null>(null);
  // Back, forward or a link changed the search in the URL: show it in the box
  if (shownQ !== q) {
    setShownQ(q);
    setSearch(q);
  }

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(ADMIN_MONEY_PAGE_SIZE);
  const filters: AdminPaymentFilters = {
    status: status || undefined,
    q: q || undefined,
    from: from || undefined,
    to: to || undefined,
    needs_refund: needsRefund || undefined,
    engagement_id: engagement || undefined,
  };
  const { payload, isLoading, isError, error, refetch } = useAdminPayments(filters, page, size);
  const totals = payload?.totals;
  const items = payload?.items ?? [];
  const canRefund = can("payments.refund");

  const download = async () => {
    setExportError(null);
    try {
      await exportCsv({ status: filters.status, q: filters.q, from: filters.from, to: filters.to, needs_refund: filters.needs_refund });
    } catch (err) {
      setExportError(getErrorMessage(err, "Could not export payments"));
    }
  };

  return (
    <AdminPage
      title="Payments · ክፍያዎች"
      description="Every online payment clients made for hires. The commission and the VAT on it are deducted and the rest is added to the provider's earnings, which they withdraw through a payout. Refunds always need a second staff member to approve."
    >
      {payload && (
        <p className="text-muted-foreground mb-3 text-xs">
          {MODE_LABEL[payload.mode]}
          {payload.mode === "chapa" && payload.test_mode ? " (test key)" : ""} · commission {payload.commission_percent}%
          {payload.test_payments > 0 && ` · ${payload.test_payments} test payments left out of the totals`}
        </p>
      )}
      <div className={cn(STAT_STRIP, "mb-2 grid-cols-2 md:grid-cols-3 lg:grid-cols-5")}>
        <StatTile label="Paid payments" value={totals ? totals.paid_count : "…"} href="?status=success" />
        <StatTile label="Gross collected" value={totals ? birr(totals.gross) : "…"} hint={totals ? `${birr(totals.price)} price + ${birr(totals.provider_vat)} provider VAT` : undefined} />
        <StatTile label="Our commission" value={totals ? birr(totals.commission) : "…"} hint={totals ? `+ ${birr(totals.commission_vat)} VAT on it` : undefined} />
        <StatTile label="To providers" value={totals ? birr(totals.to_providers) : "…"} hint="Includes the provider VAT they file" />
        <StatTile label="Chapa fees" value={totals ? birr(totals.gateway_fees) : "…"} hint="Charged by the payment service" />
        <StatTile label="Refunded" value={totals ? birr(totals.refunded) : "…"} hint={totals ? `${birr(totals.commission_refunded)} of it was commission and VAT` : undefined} />
        <StatTile label="Net commission" value={totals ? birr(totals.net_commission) : "…"} hint="Commission and its VAT, after refunds" />
        <StatTile
          label="Needs refund"
          value={totals ? totals.needs_refund : "…"}
          hint={totals?.unapplied ? `${birr(totals.unapplied)} received but not credited` : undefined}
          href="?refund=1"
          tone={totals?.needs_refund ? "attention" : "default"}
        />
        <StatTile label="Pending" value={totals ? totals.pending : "…"} href="?status=pending" tone={totals?.pending ? "attention" : "default"} />
        <StatTile label="Failed" value={totals ? totals.failed : "…"} href="?status=failed" />
      </div>
      <p className="text-muted-foreground mb-4 text-[11px]">
        Gross = commission + VAT on commission + to providers, for payments credited to a provider. The tiles follow the search and dates.
      </p>

      <form
        className="mb-3 flex flex-wrap items-end gap-2 text-xs"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          set({ q: search.trim() || null });
        }}
      >
        <div className="min-w-0 flex-1 sm:max-w-xs">
          <label htmlFor="pay-q" className="block font-medium">Search</label>
          <Input id="pay-q" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Reference, job, client or provider" />
        </div>
        <div>
          <label htmlFor="pay-from" className="block font-medium">From</label>
          <Input id="pay-from" type="date" value={from} max={to || undefined} onChange={(e) => set({ from: e.target.value || null })} className="w-36" />
        </div>
        <div>
          <label htmlFor="pay-to" className="block font-medium">To</label>
          <Input id="pay-to" type="date" value={to} min={from || undefined} onChange={(e) => set({ to: e.target.value || null })} className="w-36" />
        </div>
        <Button type="submit" size="sm">Search</Button>
        <label className="flex items-center gap-1.5 pb-1.5">
          <input type="checkbox" className="accent-primary" checked={needsRefund} onChange={(e) => set({ refund: e.target.checked ? "1" : null })} />
          Needs refund
        </label>
        {can("payments.export") && (
          <Button type="button" size="sm" variant="outline" onClick={download}>Export CSV</Button>
        )}
      </form>
      {exportError && <p className="text-destructive mb-2 text-xs" role="alert">{exportError}</p>}
      {engagement && (
        <p className="mb-3 text-xs">
          Showing the payments of one hire.{" "}
          <button type="button" className="text-primary hover:underline" onClick={() => set({ engagement: null })}>Show all</button>
        </p>
      )}

      <div role="group" aria-label="Filter by status" className="mb-3 flex flex-wrap gap-2 text-xs">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            aria-pressed={status === f.value}
            onClick={() => set({ status: f.value || null })}
            className={cn("rounded-full border px-3 py-1", status === f.value ? "border-primary bg-secondary text-primary font-medium" : "border-border")}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState error={error} message={getErrorMessage(error, "Could not load payments")} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title={needsRefund ? "No payments need a refund" : "No payments match"} />
      ) : (
        <ul className="space-y-2">
          {items.map((p) => (
            <PaymentCard key={p.tx_ref} p={p} canRefund={canRefund} />
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
    </AdminPage>
  );
}
