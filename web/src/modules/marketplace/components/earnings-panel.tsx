"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { MONEY_PAGE_SIZE, formatETB, useMyEarnings, useMyLedger, useMyPayouts, useRequestPayout } from "@cn/core/api/payments";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { EmptyState, ErrorState, Field, LoadingState, formatDate } from "@cn/ui/guday/shared";
import type { Earnings, LedgerEntry, Payout } from "@cn/core/types/payments";
import { PayoutCard } from "@/modules/marketplace/components/payout-card";
import { PayoutStatusBadge, bankLine } from "@cn/ui/marketplace/payout-status";

function Section({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("border-border bg-card rounded-xl border p-5", className)}>
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Tile({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="border-border bg-card rounded-xl border p-4">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{formatETB(value)}</p>
      {hint && <p className="text-muted-foreground mt-0.5 text-[11px] leading-snug">{hint}</p>}
    </div>
  );
}

function Summary({ e }: { e: Earnings }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="border-primary/40 bg-secondary/50 rounded-xl border p-5 sm:col-span-2 lg:col-span-4">
        <p className="text-muted-foreground text-xs">Available to withdraw · ለማውጣት ዝግጁ</p>
        <p className="text-gov-ink mt-1 text-3xl font-bold tabular-nums">{formatETB(e.available)}</p>
        <p className="text-muted-foreground mt-1 text-xs">
          What clients paid you, after the {e.commission_percent}% platform commission and the VAT on it, minus what you already withdrew or asked for
          {e.refunded ? ", and minus refunds to clients" : ""}.
        </p>
        {e.available < 0 && (
          <p className="mt-1 text-xs text-amber-800" role="note">
            A refund to a client took back more than you had. This is taken from your next earnings before you can withdraw again.
          </p>
        )}
      </div>
      {!!e.test_balance && (
        <div className="border-gov-yellow/60 bg-gov-yellow/10 rounded-xl border p-4 sm:col-span-2 lg:col-span-4" role="note">
          <p className="text-xs font-medium">Test earnings: {formatETB(e.test_balance)}</p>
          <p className="text-muted-foreground mt-0.5 text-[11px]">
            From test payments made before real payments started. No real money was collected, so they can&apos;t be withdrawn.
          </p>
        </div>
      )}
      <Tile label="Waiting for payout" value={e.in_payout} hint={e.in_payout ? "Held until the payout is paid or rejected" : undefined} />
      <Tile label="Earned this month" value={e.earned_this_month} />
      <Tile label="Earned in total" value={e.earned_total} />
      <Tile label="Paid out" value={e.paid_out} />
    </div>
  );
}

function Withdraw({ e }: { e: Earnings }) {
  const { request, isPending } = useRequestPayout();
  const [typed, setTyped] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Payout | null>(null);
  const account = e.payout_account;

  if (!account.ready) {
    return (
      <Section title="Withdraw · ገንዘብ ማውጣት">
        {account.mode === "off" ? (
          <p className="text-muted-foreground text-sm">Online payments are not switched on yet, so there is nothing to withdraw.</p>
        ) : (
          <>
            <p className="text-muted-foreground mb-3 text-xs leading-relaxed">
              Add the bank account your money should go to. You can withdraw once it is saved.
            </p>
            <PayoutCard className="border-0 bg-transparent p-0" />
          </>
        )}
      </Section>
    );
  }

  const value = typed ?? (e.available > 0 ? e.available.toFixed(2) : "");
  const amount = Number(value);
  const tooLow = e.available < e.min_payout;
  const problem =
    !value || !Number.isFinite(amount) || amount <= 0
      ? "Enter an amount"
      : amount < e.min_payout
        ? `The smallest withdrawal is ${formatETB(e.min_payout)}`
        : amount > e.available
          ? `You can withdraw up to ${formatETB(e.available)}`
          : null;
  const target = bankLine(account.bank_name, account.account_last4);

  return (
    <Section title="Withdraw · ገንዘብ ማውጣት">
      {tooLow ? (
        <p className="text-muted-foreground text-sm">
          You can withdraw once at least {formatETB(e.min_payout)} is available. You have {formatETB(e.available)} now.
        </p>
      ) : (
        <form
          className="space-y-3"
          onSubmit={async (ev) => {
            ev.preventDefault();
            if (problem) return;
            setError(null);
            setDone(null);
            try {
              const payout = await request(Math.round(amount * 100) / 100);
              setDone(payout);
              setTyped(null);
            } catch (err) {
              setError(getErrorMessage(err, "Could not request the withdrawal"));
            }
          }}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <Field label="Amount (ETB)" htmlFor="withdraw-amount" className="sm:w-64">
              <Input
                id="withdraw-amount"
                type="number"
                inputMode="decimal"
                step="0.01"
                min={e.min_payout}
                max={e.available}
                value={value}
                onChange={(ev) => setTyped(ev.target.value)}
                aria-invalid={!!value && !!problem}
              />
            </Field>
            <Button type="submit" disabled={!!problem} loading={isPending} className="h-auto max-w-full py-2 whitespace-normal">
              Withdraw to {target}
            </Button>
          </div>
          {value && problem && <p className="text-destructive text-xs">{problem}</p>}
          <p className="text-muted-foreground text-xs">
            Minimum {formatETB(e.min_payout)}. Our team approves withdrawals, usually within one working day.
          </p>
        </form>
      )}
      {error && <p className="text-destructive mt-3 text-xs" role="alert">{error}</p>}
      {done && (
        <p className="border-primary/40 bg-secondary/60 mt-3 rounded-md border p-3 text-sm" role="status">
          Withdrawal of {formatETB(done.amount)} to {bankLine(done.bank_name, done.account_last4)} requested. We will notify you when it is sent.
        </p>
      )}
      <p className="text-muted-foreground mt-3 text-[11px]">
        Paid to {target}
        {account.account_name ? ` (${account.account_name})` : ""}. Change the account on the Edit profile tab.
      </p>
    </Section>
  );
}

const linkClass = "text-primary text-[11px] font-medium whitespace-nowrap hover:underline";

type PageControls = { page: number; total: number; onPage: (page: number) => void };

function PayoutHistory({ payouts, pager }: { payouts: Payout[]; pager: PageControls }) {
  return (
    <Section title="Withdrawals" className="border-0 p-0 md:p-0">
      {!payouts.length ? (
        <p className="text-muted-foreground text-sm">No withdrawals yet.</p>
      ) : (
        <div className="max-w-full overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">Date</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Amount</th>
                <th scope="col" className="py-2 pr-3 font-medium">To</th>
                <th scope="col" className="py-2 pr-3 font-medium">Status</th>
                <th scope="col" className="py-2 pr-3 font-medium">Reference</th>
                <th scope="col" className="py-2 font-medium"><span className="sr-only">Receipt</span></th>
              </tr>
            </thead>
            <tbody>
              {payouts.map((p) => (
                <tr key={p.id} className="border-border border-t align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {formatDate(p.created_at)}
                    {p.paid_at && <span className="text-muted-foreground block text-[11px]">paid {formatDate(p.paid_at)}</span>}
                  </td>
                  <td className="py-2 pr-3 text-right font-medium tabular-nums whitespace-nowrap">{formatETB(p.amount)}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">{bankLine(p.bank_name, p.account_last4)}</td>
                  <td className="py-2 pr-3">
                    <PayoutStatusBadge status={p.status} />
                    {p.status === "rejected" && p.note && <span className="text-muted-foreground mt-1 block max-w-xs text-[11px]">{p.note}</span>}
                    {p.status === "failed" && <span className="text-muted-foreground mt-1 block text-[11px]">Our team will contact you.</span>}
                  </td>
                  <td className="py-2 pr-3 font-mono text-[11px] break-all">{p.gateway_reference ?? p.reference ?? ""}</td>
                  <td className="py-2 text-right">
                    {p.status === "paid" && (
                      <Link href={`/receipts/payout/${encodeURIComponent(p.id)}`} className={linkClass} aria-label={`Receipt for the ${formatETB(p.amount)} withdrawal`}>
                        Receipt
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={pager.page} pageSize={MONEY_PAGE_SIZE} total={pager.total} onPage={pager.onPage} />
    </Section>
  );
}

/** The payout behind a ledger row: by id when the API gives it, else by reference. */
function payoutFor(entry: LedgerEntry, payouts: Payout[]): Payout | undefined {
  if (entry.kind !== "payout") return undefined;
  return (
    payouts.find((p) => entry.payout_id && p.id === entry.payout_id) ??
    payouts.find((p) => p.reference && p.reference === entry.payout_reference)
  );
}

function describe(entry: LedgerEntry, payouts: Payout[]): string {
  if (entry.kind === "earning") {
    const client = entry.client_name?.trim().split(/\s+/)[0];
    return [entry.job_title ?? "Paid job", client].filter(Boolean).join(" · ");
  }
  if (entry.kind === "payout") {
    const payout = payoutFor(entry, payouts);
    return payout ? `Payout to ${bankLine(payout.bank_name, payout.account_last4)}` : (entry.note ?? "Payout");
  }
  if (entry.kind === "refund") {
    return `Refund to the client · ${entry.job_title ?? "a job"}`;
  }
  return entry.note ?? "Adjustment";
}

function LedgerLink({ entry, payouts }: { entry: LedgerEntry; payouts: Payout[] }) {
  if (entry.kind === "earning" && entry.tx_ref) {
    return (
      <Link
        href={`/receipts/statement/${encodeURIComponent(entry.tx_ref)}`}
        className={linkClass}
        aria-label={`Statement for ${entry.job_title ?? "this job"}`}
      >
        Statement
      </Link>
    );
  }
  if (entry.kind === "refund" && entry.refund_id) {
    return (
      <Link href={`/receipts/refund/${encodeURIComponent(entry.refund_id)}`} className={linkClass} aria-label="Refund receipt">
        Refund
      </Link>
    );
  }
  if (entry.kind === "payout") {
    const payout = payoutFor(entry, payouts);
    const id = entry.payout_id ?? payout?.id;
    if (id && (!payout || payout.status === "paid")) {
      return (
        <Link href={`/receipts/payout/${encodeURIComponent(id)}`} className={linkClass} aria-label="Receipt for this withdrawal">
          Receipt
        </Link>
      );
    }
  }
  return null;
}

/** `payouts` is only for looking up the payout behind a ledger row (bank and status). */
function Ledger({ entries, payouts, pager }: { entries: LedgerEntry[]; payouts: Payout[]; pager: PageControls }) {
  return (
    <Section title="Earnings history" className="border-0 p-0 md:p-0">
      {!entries.length ? (
        <p className="text-muted-foreground text-sm">No earnings yet. You earn when a client pays for delivered work.</p>
      ) : (
        <div className="max-w-full overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">Date</th>
                <th scope="col" className="py-2 pr-3 font-medium">What</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Client paid</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Commission</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Amount</th>
                <th scope="col" className="py-2 font-medium"><span className="sr-only">Statement or receipt</span></th>
              </tr>
            </thead>
            <tbody>
              {entries.map((l) => (
                <tr key={l.id} className="border-border border-t align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">{formatDate(l.created_at)}</td>
                  <td className="py-2 pr-3">
                    {describe(l, payouts)}
                    {l.is_test && <span className="bg-muted ml-1 rounded px-1 text-[10px]">Test</span>}
                    {l.kind === "earning" && !!l.provider_vat && (
                      <span className="text-muted-foreground block text-[11px]">incl. VAT you collected {formatETB(l.provider_vat)}</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{l.kind === "earning" && l.gross != null ? formatETB(l.gross) : ""}</td>
                  <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">
                    {l.kind === "earning" && l.commission != null ? (
                      <>
                        -{formatETB(l.commission)}
                        {!!l.commission_vat && (
                          <span className="text-muted-foreground block text-[11px]">+ VAT {formatETB(l.commission_vat)}</span>
                        )}
                      </>
                    ) : (
                      ""
                    )}
                  </td>
                  <td
                    className={cn(
                      "py-2 pr-3 text-right font-medium tabular-nums whitespace-nowrap",
                      l.amount >= 0 ? "text-emerald-700" : "text-foreground",
                    )}
                  >
                    {l.amount >= 0 ? "+" : "-"}
                    {formatETB(Math.abs(l.amount))}
                  </td>
                  <td className="py-2 text-right">
                    <LedgerLink entry={l} payouts={payouts} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={pager.page} pageSize={MONEY_PAGE_SIZE} total={pager.total} onPage={pager.onPage} />
    </Section>
  );
}

type HistoryTab = "earnings" | "withdrawals";

/** Earnings history and withdrawals as side tabs: a vertical list on md+, a row above the content on phones. */
function HistoryTabs({ e }: { e: Earnings }) {
  const [tab, setTabState] = useState<HistoryTab>("earnings");
  const [page, setPage] = useUrlPage();
  const setTab = (t: HistoryTab) => {
    if (t === tab) return;
    setTabState(t);
    setPage(0);
  };
  const base = useId();
  // Page 0 of the other tab gives its count
  const ledger = useMyLedger(tab === "earnings" ? page : 0);
  const payouts = useMyPayouts(tab === "withdrawals" ? page : 0);
  const ledgerTotal = ledger.data?.payload.total;
  const payoutsTotal = payouts.data?.payload.total;
  const tabs: { key: HistoryTab; label: string; count: number | undefined }[] = [
    { key: "earnings", label: "Earnings history", count: ledgerTotal },
    { key: "withdrawals", label: "Withdrawals", count: payoutsTotal },
  ];
  const current = tab === "earnings" ? ledger : payouts;
  // Recent payouts from the summary plus this page: enough to describe a payout row in the ledger
  const knownPayouts = [...(payouts.data?.payload.items ?? []), ...(e.payouts ?? [])];
  const pager: PageControls = { page, total: current.data?.payload.total ?? 0, onPage: setPage };
  const onKeyDown = (ev: React.KeyboardEvent<HTMLButtonElement>) => {
    const keys = ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Home", "End"];
    if (!keys.includes(ev.key)) return;
    ev.preventDefault();
    const i = tabs.findIndex((t) => t.key === tab);
    const next =
      ev.key === "Home" ? 0 : ev.key === "End" ? tabs.length - 1 : ev.key === "ArrowDown" || ev.key === "ArrowRight" ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
    setTab(tabs[next].key);
    document.getElementById(`${base}-tab-${tabs[next].key}`)?.focus();
  };

  return (
    <section className="border-border bg-card flex min-w-0 flex-col gap-4 rounded-xl border p-4 md:flex-row md:gap-6 md:p-5">
      <div role="tablist" aria-label="Money history" aria-orientation="vertical" className="flex min-w-0 gap-1 md:w-48 md:shrink-0 md:flex-col">
        {tabs.map((t) => {
          const active = t.key === tab;
          return (
            <button
              key={t.key}
              id={`${base}-tab-${t.key}`}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={`${base}-panel-${t.key}`}
              tabIndex={active ? 0 : -1}
              onClick={() => setTab(t.key)}
              onKeyDown={onKeyDown}
              className={cn(
                "flex flex-1 items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm font-medium md:flex-none",
                active ? "bg-secondary text-gov-ink" : "text-muted-foreground hover:bg-secondary/50",
              )}
            >
              {t.label}
              {t.count != null && <span className="text-muted-foreground text-[11px] tabular-nums">{t.count}</span>}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${base}-panel-${tab}`}
        aria-labelledby={`${base}-tab-${tab}`}
        tabIndex={0}
        className="w-full min-w-0 flex-1 md:w-auto md:border-l md:pl-6"
      >
        {current.isLoading ? (
          <LoadingState />
        ) : current.isError ? (
          <ErrorState message={current.error?.message ?? "Could not load this list"} onRetry={() => current.refetch()} />
        ) : tab === "earnings" ? (
          <Ledger entries={ledger.data?.payload.items ?? []} payouts={knownPayouts} pager={pager} />
        ) : (
          <PayoutHistory payouts={payouts.data?.payload.items ?? []} pager={pager} />
        )}
      </div>
    </section>
  );
}

/** Provider balance, withdrawals and the money ledger. */
export function EarningsPanel() {
  const { data, isLoading, isError, error, refetch } = useMyEarnings();
  const e = data?.payload;
  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={error?.message ?? "Could not load your earnings"} onRetry={() => refetch()} />;
  if (!e) return <EmptyState title="No earnings yet" />;
  return (
    <div className="min-w-0 space-y-4">
      <Summary e={e} />
      <Withdraw e={e} />
      <HistoryTabs e={e} />
    </div>
  );
}
