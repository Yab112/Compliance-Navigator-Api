"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ADMIN_MONEY_PAGE_SIZE, formatBirr, useAdminPayments } from "@/api/payments";
import { Badge } from "@/components/ui/badge";
import { Pager, useUrlPage } from "@/components/ui/pager";
import { cn } from "@/lib/utils";
import { AdminPage } from "@/modules/admin/components/admin-page";
import { StatTile } from "@/modules/admin/shared/stat-tile";
import { EmptyState, ErrorState, LoadingState, formatDateTime } from "@/modules/guday/components/shared";
import type { PaymentStatus, PaymentsMode } from "@/types/payments";

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

const birr = (n: number) => `${formatBirr(n)} ETB`;

export function AdminPayments() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const raw = params.get("status") ?? "";
  const status = (FILTERS.some((f) => f.value === raw) ? raw : "") as PaymentStatus | "";
  const setStatus = (v: string) => {
    const next = new URLSearchParams(params.toString());
    if (v) next.set("status", v);
    else next.delete("status");
    next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const [page, setPage] = useUrlPage();
  const { payload, isLoading, isError, error, refetch } = useAdminPayments(status || undefined, page);
  const totals = payload?.totals;
  const items = payload?.items ?? [];

  return (
    <AdminPage
      title="Payments · ክፍያዎች"
      description="Every online payment clients made for hires. Totals cover all payments; the platform commission is deducted and the rest is added to the provider's earnings, which they withdraw through a payout."
    >
      {payload && (
        <p className="text-muted-foreground mb-3 text-xs">
          {MODE_LABEL[payload.mode]} · commission {payload.commission_percent}%
        </p>
      )}
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Paid payments" value={totals ? totals.paid_count : "…"} href="?status=success" />
        <StatTile label="Gross collected" value={totals ? birr(totals.gross) : "…"} />
        <StatTile label="Our commission" value={totals ? birr(totals.commission) : "…"} />
        <StatTile label="To providers" value={totals ? birr(totals.to_providers) : "…"} />
        <StatTile label="Pending" value={totals ? totals.pending : "…"} href="?status=pending" tone={totals?.pending ? "attention" : "default"} />
        <StatTile label="Failed" value={totals ? totals.failed : "…"} href="?status=failed" />
      </div>

      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setStatus(f.value)}
            className={cn("rounded-full border px-3 py-1", status === f.value ? "border-primary bg-secondary text-primary font-medium" : "border-border")}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load payments"} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title="No payments yet" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="py-2 pr-3 font-medium">When</th>
                <th className="py-2 pr-3 font-medium">Hire</th>
                <th className="py-2 pr-3 font-medium">Client</th>
                <th className="py-2 pr-3 font-medium">Provider</th>
                <th className="py-2 pr-3 text-right font-medium">Amount</th>
                <th className="py-2 pr-3 text-right font-medium">Commission</th>
                <th className="py-2 pr-3 text-right font-medium">To provider</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 font-medium">Reference</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.tx_ref} className="border-border border-t align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {formatDateTime(p.created_at)}
                    {p.verified_at && <span className="text-muted-foreground block text-[11px]">verified {formatDateTime(p.verified_at)}</span>}
                  </td>
                  <td className="py-2 pr-3">{p.title}</td>
                  <td className="py-2 pr-3">{p.client_name}</td>
                  <td className="py-2 pr-3">
                    {p.provider_slug ? (
                      <Link href={`/providers/${p.provider_slug}`} className="text-primary hover:underline">{p.provider_name}</Link>
                    ) : (
                      p.provider_name
                    )}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{formatBirr(p.amount)} {p.currency}</td>
                  <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{formatBirr(p.commission_amount)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{formatBirr(p.provider_amount)}</td>
                  <td className="py-2 pr-3">
                    <Badge className={STATUS[p.status]?.className}>{STATUS[p.status]?.label ?? p.status}</Badge>
                    {p.payment_method && <span className="text-muted-foreground block text-[11px]">{p.payment_method}</span>}
                  </td>
                  <td className="py-2 font-mono text-[11px]">
                    {p.tx_ref}
                    <span className="text-muted-foreground block">
                      {p.gateway}
                      {p.gateway_reference ? ` · ${p.gateway_reference}` : ""}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={page} pageSize={ADMIN_MONEY_PAGE_SIZE} total={payload?.total ?? 0} onPage={setPage} />
    </AdminPage>
  );
}
