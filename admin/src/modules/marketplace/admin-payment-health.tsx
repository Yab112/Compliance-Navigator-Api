"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  ADMIN_MONEY_PAGE_SIZE,
  formatETB,
  usePaymentHealth,
  usePaymentHealthCheck,
  usePaymentHealthErrors,
} from "@cn/core/api/payments";
import { getErrorMessage } from "@cn/core/lib/errors";
import { formatDateTime, timeAgo } from "@cn/core/lib/format";
import { cn } from "@cn/core/lib/utils";
import { Badge } from "@cn/ui/badge";
import { Button } from "@cn/ui/button";
import { EmptyState, LoadingState } from "@cn/ui/guday/shared";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import type {
  GatewayCallError,
  GatewayLiveCheck,
  GatewayOperation,
  PaymentAttentionItem,
  PaymentHealthState,
  PaymentHealthStatus,
  PaymentsMode,
} from "@cn/core/types/payments";
import { AdminPage } from "@/modules/components/admin-page";
import { useCan } from "@/modules/access/api";
import { STAT_STRIP, StatTile } from "@/modules/shared/stat-tile";
import { ErrorState } from "@/modules/shared/states";

const PERIODS = [
  { value: "1h", hours: 1, label: "Last hour" },
  { value: "24h", hours: 24, label: "Last 24 hours" },
  { value: "7d", hours: 168, label: "Last 7 days" },
] as const;

const STATE: Record<PaymentHealthState, { dot: string; text: string }> = {
  healthy: { dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-400" },
  degraded: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-400" },
  down: { dot: "bg-red-500", text: "text-red-700 dark:text-red-400" },
  no_calls: { dot: "bg-zinc-400", text: "text-muted-foreground" },
};

const OPERATION: Record<GatewayOperation, string> = {
  initialize: "Start checkout",
  verify: "Check payment",
  transfer: "Send payout",
  verify_transfer: "Check payout",
  refund: "Send refund",
  verify_refund: "Check refund",
  banks: "Bank list",
  other: "Other",
};

const MODE_LABEL: Record<PaymentsMode, string> = {
  off: "Online payments are off, so nothing is sent to Chapa.",
  simulated: "Test mode (simulated gateway): nothing is sent to Chapa, so there are no calls to show.",
  chapa: "Chapa with a live key: real money moves.",
};

const PROBLEM: Record<PaymentAttentionItem["problem"], { label: string; className: string }> = {
  needs_check: { label: "Check with Chapa", className: "bg-red-100 text-red-900" },
  failed: { label: "Failed", className: "bg-zinc-200 text-zinc-700" },
  stuck: { label: "Still pending", className: "bg-amber-100 text-amber-900" },
};

const KIND: Record<PaymentAttentionItem["kind"], string> = { payment: "Payment", payout: "Payout", refund: "Refund" };

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "-";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function percent(rate: number): string {
  if (!rate) return "0%";
  const p = rate * 100;
  return `${p < 10 ? p.toFixed(1) : Math.round(p)}%`;
}

function age(seconds: number): string {
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))} min`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86400)} days`;
}

/** Where staff deal with a payment, payout or refund: payments (and their refunds) by reference, payouts by status. */
function moneyLink(kind: "payment" | "payout" | "refund", txRef: string | undefined, status: string): string | null {
  if (kind === "payout") return status === "requested" ? "/marketplace/payouts" : `/marketplace/payouts?status=${status}`;
  return txRef ? `/marketplace/payments?q=${encodeURIComponent(txRef)}` : null;
}

function StatusLine({ status }: { status: PaymentHealthStatus }) {
  const { check, isPending } = usePaymentHealthCheck();
  const [result, setResult] = useState<GatewayLiveCheck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const style = STATE[status.status];
  const run = async () => {
    setError(null);
    setResult(null);
    try {
      setResult(await check());
    } catch (err) {
      setError(getErrorMessage(err, "Could not check Chapa"));
    }
  };
  return (
    <section aria-label="Chapa status" className="border-border mb-6 border-b pb-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="flex items-center gap-2 text-base font-semibold">
            <span className={cn("size-2.5 shrink-0 rounded-full", style.dot)} aria-hidden />
            <span className={style.text}>Chapa: {status.label}</span>
          </p>
          <p className="max-w-3xl text-sm">{status.reason}</p>
          <p className="text-muted-foreground text-xs">
            Last successful call:{" "}
            {status.last_success_at ? (
              <span title={formatDateTime(status.last_success_at)}>{timeAgo(status.last_success_at)}</span>
            ) : (
              "never"
            )}
            {status.last_call_at && <> · last call {timeAgo(status.last_call_at)}</>} · {status.mode === "chapa" && status.test_mode ? "Chapa with a TEST key: no real money moves." : MODE_LABEL[status.mode]}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 text-right">
          <Button size="sm" variant="outline" loading={isPending} onClick={run}>Check Chapa now</Button>
          <p className="text-muted-foreground max-w-xs text-[11px]">Asks Chapa for its bank list. Moves no money.</p>
        </div>
      </div>
      {result && (
        <p role="status" className={cn("mt-2 text-xs", result.ok === false ? "text-destructive" : result.ok ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground")}>
          {result.ok === null
            ? result.message
            : result.ok
              ? `${result.message} (HTTP ${result.http_status ?? "?"})`
              : `Chapa did not answer properly after ${formatMs(result.latency_ms)}${result.http_status ? ` (HTTP ${result.http_status})` : " (no answer)"}: ${result.error ?? "no message"}`}
        </p>
      )}
      {error && <p role="alert" className="text-destructive mt-2 text-xs">{error}</p>}
    </section>
  );
}

function AttentionList({ items, showsPayouts }: { items: PaymentAttentionItem[]; showsPayouts: boolean }) {
  return (
    <section aria-labelledby="attention-h" className="mb-8">
      <h2 id="attention-h" className="mb-1 text-sm font-semibold">Needs attention</h2>
      <p className="text-muted-foreground mb-2 text-xs">
        Payouts and refunds Chapa has not confirmed (the money may have moved), ones that failed in the last 7 days, and
        checkouts still pending after 30 minutes.{!showsPayouts && " Payouts are left out: you can't see payouts."}
      </p>
      {!items.length ? (
        <p className="text-muted-foreground border-border border-y py-3 text-xs">Nothing needs a person right now.</p>
      ) : (
        <ul className="border-border border-y">
          {items.map((i) => {
            const href = moneyLink(i.kind, i.tx_ref, i.status);
            const problem = PROBLEM[i.problem];
            return (
              <li key={`${i.kind}-${i.id}`} className="border-border flex flex-wrap items-start justify-between gap-3 border-t py-2 text-xs first:border-t-0">
                <div className="min-w-0 space-y-0.5">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{KIND[i.kind]}</span>
                    <Badge className={problem.className}>{problem.label}</Badge>
                    {href ? (
                      <Link href={href} className="text-primary font-mono hover:underline">{i.reference}</Link>
                    ) : (
                      <span className="font-mono">{i.reference}</span>
                    )}
                    {i.is_test && <span className="bg-muted rounded px-1.5 text-[10px]">Test</span>}
                  </p>
                  <p className="text-muted-foreground">
                    {i.who ? `${i.who} · ` : ""}
                    {age(i.age_seconds)} ago · {formatDateTime(i.since)}
                  </p>
                  <p>{i.reason}</p>
                </div>
                <p className="text-sm font-semibold tabular-nums">{formatETB(i.amount)}</p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function ErrorReference({ e }: { e: GatewayCallError }) {
  const b = e.belongs_to;
  if (!e.reference) return <span className="text-muted-foreground">-</span>;
  const href = b ? moneyLink(b.kind, "tx_ref" in b ? b.tx_ref : undefined, b.status) : null;
  return (
    <span className="flex flex-col">
      {href ? (
        <Link href={href} className="text-primary font-mono break-all hover:underline">{e.reference}</Link>
      ) : (
        <span className="font-mono break-all">{e.reference}</span>
      )}
      {b && <span className="text-muted-foreground text-[10px]">{KIND[b.kind]}, now {b.status.replace("_", " ")}</span>}
    </span>
  );
}

function RecentErrors() {
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(ADMIN_MONEY_PAGE_SIZE);
  const { payload, isLoading, isError, error, refetch } = usePaymentHealthErrors(page, size);
  const items = payload?.items ?? [];
  return (
    <section aria-labelledby="errors-h">
      <h2 id="errors-h" className="mb-1 text-sm font-semibold">Recent errors</h2>
      <p className="text-muted-foreground mb-2 text-xs">
        Every Chapa call that did not succeed, newest first, kept for 90 days. &quot;May have gone through&quot; means Chapa
        did not answer clearly, so the request may have been carried out: check before doing it again.
      </p>
      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState error={error} message={getErrorMessage(error, "Could not load the errors")} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title="No errors recorded" />
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="py-2 pr-3 font-medium">Time</th>
                <th className="py-2 pr-3 font-medium">Operation</th>
                <th className="py-2 pr-3 font-medium">Reference</th>
                <th className="py-2 pr-3 font-medium" title="The HTTP status Chapa answered with; none when it never answered">HTTP</th>
                <th className="py-2 pr-3 font-medium">Chapa&apos;s message</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-border border-t align-top">
                  <td className="py-2 pr-3 whitespace-nowrap" title={formatDateTime(e.created_at)}>
                    {formatDateTime(e.created_at)}
                    <span className="text-muted-foreground block text-[10px]">{formatMs(e.duration_ms)}</span>
                  </td>
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {OPERATION[e.operation]}
                    {e.is_test && <span className="bg-muted ml-1 rounded px-1.5 text-[10px]">Test key</span>}
                  </td>
                  <td className="py-2 pr-3"><ErrorReference e={e} /></td>
                  <td className="py-2 pr-3 tabular-nums">{e.http_status ?? <span className="text-muted-foreground">none</span>}</td>
                  <td className="py-2 pr-3">
                    <span className="break-words">{e.error ?? "No message"}</span>
                    {e.uncertain && (
                      <Badge className="ml-2 bg-amber-100 text-amber-900" title="Chapa did not answer clearly, so the request may have been carried out">
                        May have gone through
                      </Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
    </section>
  );
}

export function AdminPaymentHealth() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { can } = useCan();
  const period = PERIODS.find((p) => p.value === params.get("period")) ?? PERIODS[1];
  const setPeriod = (value: string) => {
    const next = new URLSearchParams(params.toString());
    if (value === "24h") next.delete("period");
    else next.set("period", value);
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const { payload, isLoading, isError, error, refetch } = usePaymentHealth(period.hours);
  const totals = payload?.summary.totals;
  const operations = payload?.summary.operations ?? [];

  return (
    <AdminPage
      title="Payment health · የክፍያ ጤና"
      description="Whether Chapa is answering us, every call that went wrong, and money that needs a person now. Every call to Chapa is recorded (never the secret key or account numbers) and kept for 90 days. This page refreshes every minute."
    >
      {isLoading ? (
        <LoadingState />
      ) : isError || !payload ? (
        <ErrorState error={error} message={getErrorMessage(error, "Could not load payment health")} onRetry={() => refetch()} />
      ) : (
        <>
          <StatusLine status={payload.status} />

          <div role="group" aria-label="Period" className="mb-3 flex flex-wrap gap-2 text-xs">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                type="button"
                aria-pressed={period.value === p.value}
                onClick={() => setPeriod(p.value)}
                className={cn("rounded-full border px-3 py-1", period.value === p.value ? "border-primary bg-secondary text-primary font-medium" : "border-border")}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className={cn(STAT_STRIP, "mb-2 grid-cols-2 lg:grid-cols-4")}>
            <StatTile label="Calls to Chapa" value={totals ? totals.calls : "…"} hint={totals?.test_calls ? `${totals.test_calls} with a test key` : undefined} />
            <StatTile
              label="Failed"
              value={totals ? totals.failures : "…"}
              hint={totals ? `${totals.faults} no answer or server error · ${totals.refusals} refused by Chapa` : undefined}
              tone={totals?.faults ? "attention" : "default"}
            />
            <StatTile label="Failure rate" value={totals ? percent(totals.failure_rate) : "…"} />
            <StatTile label="Slowest 5% took over" value={totals ? formatMs(totals.p95_ms) : "…"} hint={totals ? `Average ${formatMs(totals.avg_ms)}` : undefined} />
          </div>
          <p className="text-muted-foreground mb-6 text-[11px]">
            Refused means Chapa answered and said no (for example a checkout not paid yet or a wrong account number). Only no
            answer, server errors and a refused key count against Chapa&apos;s status.
          </p>

          <section aria-labelledby="ops-h" className="mb-8">
            <h2 id="ops-h" className="mb-2 text-sm font-semibold">By operation</h2>
            {!operations.length ? (
              <p className="text-muted-foreground border-border border-y py-3 text-xs">No calls to Chapa recorded yet.</p>
            ) : (
              <div className="relative overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-muted-foreground text-[11px]">
                    <tr>
                      <th className="py-2 pr-3 font-medium">Operation</th>
                      <th className="py-2 pr-3 text-right font-medium">Calls</th>
                      <th className="py-2 pr-3 text-right font-medium">Failed</th>
                      <th className="py-2 pr-3 text-right font-medium">Rate</th>
                      <th className="hidden py-2 pr-3 text-right font-medium sm:table-cell">Average</th>
                      <th className="py-2 pr-3 text-right font-medium" title="The slowest 5% of calls took longer than this">Slowest 5%</th>
                      <th className="hidden py-2 pr-3 font-medium md:table-cell">Last success</th>
                      <th className="hidden py-2 pr-3 font-medium md:table-cell">Last failure</th>
                    </tr>
                  </thead>
                  <tbody>
                    {operations.map((o) => (
                      <tr key={o.operation} className="border-border border-t align-top">
                        <td className="py-2 pr-3 font-medium whitespace-nowrap">{OPERATION[o.operation]}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{o.calls}</td>
                        <td className={cn("py-2 pr-3 text-right tabular-nums", o.faults > 0 && "text-destructive")}>
                          {o.failures}
                          {o.uncertain > 0 && <span className="text-muted-foreground block text-[10px]">{o.uncertain} may have gone through</span>}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{o.calls ? percent(o.failure_rate) : "-"}</td>
                        <td className="hidden py-2 pr-3 text-right tabular-nums sm:table-cell">{formatMs(o.avg_ms)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{formatMs(o.p95_ms)}</td>
                        <td className="hidden py-2 pr-3 whitespace-nowrap md:table-cell" title={formatDateTime(o.last_success_at)}>
                          {timeAgo(o.last_success_at)}
                        </td>
                        <td className="hidden py-2 pr-3 md:table-cell">
                          {o.last_failure_at ? (
                            <>
                              <span title={formatDateTime(o.last_failure_at)}>{timeAgo(o.last_failure_at)}</span>
                              <span className="text-muted-foreground block">
                                {o.last_failure_http_status ? `HTTP ${o.last_failure_http_status}: ` : ""}
                                {o.last_failure_message ?? "no message"}
                              </span>
                            </>
                          ) : (
                            <span className="text-muted-foreground">none</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <AttentionList items={payload.attention.items} showsPayouts={can("payouts.view")} />
        </>
      )}
      <RecentErrors />
    </AdminPage>
  );
}
