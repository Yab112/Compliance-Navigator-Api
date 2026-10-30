"use client";

import { useEffect, useState } from "react";
import { useBanks, useMyPayout, usePaymentsConfig, useSavePayout } from "@cn/core/api/payments";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { Field, NativeSelect } from "@cn/ui/guday/shared";
import type { PayoutAccount } from "@cn/core/types/payments";

/** How long the bank list may load before we offer a retry instead of waiting forever. */
const BANKS_SLOW_MS = 10_000;

function PayoutForm({ current, onDone, onCancel }: {
  current?: PayoutAccount;
  onDone: () => void;
  onCancel?: () => void;
}) {
  const banks = useBanks();
  const { save, isPending } = useSavePayout();
  const [bank, setBank] = useState("");
  const [number, setNumber] = useState("");
  const [name, setName] = useState(current?.account_name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [banksSlow, setBanksSlow] = useState(false);
  const [banksTry, setBanksTry] = useState(0);
  useEffect(() => {
    if (!banks.isLoading) return;
    const t = window.setTimeout(() => setBanksSlow(true), BANKS_SLOW_MS);
    return () => window.clearTimeout(t);
  }, [banks.isLoading, banksTry]);
  const retryBanks = () => {
    setBanksSlow(false);
    setBanksTry((n) => n + 1);
    void banks.refetch();
  };
  const banksFailed = banks.isError || (banksSlow && banks.isLoading);
  const items = banks.data?.payload.items ?? [];
  const valid = !!bank && /^\d{6,20}$/.test(number.replace(/\s+/g, "")) && name.trim().length >= 2;
  const verified = current?.verified_name;

  return (
    <form
      className="space-y-3"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!valid) return;
        setError(null);
        try {
          await save({ bank_code: bank, account_number: number.replace(/\s+/g, ""), account_name: name.trim() });
          onDone();
        } catch (err) {
          setError(getErrorMessage(err, "Could not save your payout account"));
        }
      }}
    >
      <p className="text-muted-foreground text-xs leading-relaxed">
        Your earnings are paid out to this account when you request a withdrawal and our team approves it. The account
        must be in your own name (or your company&apos;s). Our team checks the holder name against the name on your
        verified ID before sending money.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Bank · ባንክ" htmlFor="payout-bank" required className="sm:col-span-2">
          <NativeSelect id="payout-bank" value={bank} onChange={(e) => setBank(e.target.value)} disabled={banks.isLoading || !items.length}>
            <option value="">{banksFailed ? "Could not load banks" : banks.isLoading ? "Loading banks…" : "Choose your bank"}</option>
            {items.map((b) => (
              <option key={b.code} value={b.code}>{b.name}</option>
            ))}
          </NativeSelect>
          {banksFailed && (
            <p className="text-destructive mt-1 flex flex-wrap items-center gap-2 text-xs" role="alert">
              {banks.isError ? getErrorMessage(banks.error, "Could not load the list of banks.") : "The list of banks is taking too long to load."}
              <Button type="button" size="sm" variant="outline" loading={banks.isFetching && !banksSlow} onClick={retryBanks}>Try again</Button>
            </p>
          )}
        </Field>
        <Field label="Account number · የሂሳብ ቁጥር" htmlFor="payout-number" required>
          <Input id="payout-number" inputMode="numeric" autoComplete="off" value={number} onChange={(e) => setNumber(e.target.value)} />
        </Field>
        <Field label="Account holder name · የባለሂሳቡ ስም" htmlFor="payout-name" required>
          <Input id="payout-name" value={name} onChange={(e) => setName(e.target.value)} aria-describedby="payout-name-hint" />
          <p id="payout-name-hint" className="text-muted-foreground mt-1 text-[11px]">
            Exactly as the bank has it.
            {verified ? <> Your verified ID says <strong>{verified}</strong>.</> : null}
          </p>
        </Field>
      </div>
      {error && <p className="text-destructive text-xs" role="alert">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={!valid} loading={isPending}>Save payout account</Button>
        {onCancel && <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}

/** The bank account a provider's withdrawals are sent to. Hidden when online payments are off. */
export function PayoutCard({ className }: { className?: string }) {
  const config = usePaymentsConfig();
  const mode = config.data?.payload.mode;
  const payoutQuery = useMyPayout(!!mode && mode !== "off");
  const [editing, setEditing] = useState(false);
  if (!mode || mode === "off") return null;
  const payout = payoutQuery.data?.payload.payout;
  const commission = payout?.commission_percent ?? config.data?.payload.commission_percent ?? 0;

  return (
    <section className={cn("border-border bg-card rounded-xl border p-5", className)}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Get paid online · ክፍያ መቀበያ</h2>
        {mode === "simulated" && (
          <span className="bg-gov-yellow/40 text-gov-ink rounded px-2 py-0.5 text-[11px] font-medium">Test mode: no real money moves</span>
        )}
      </div>
      {payoutQuery.isLoading ? (
        <p className="text-muted-foreground text-xs">Loading…</p>
      ) : payoutQuery.isError ? (
        <p className="text-destructive text-xs">{payoutQuery.error?.message ?? "Could not load your payout account"}</p>
      ) : payout?.ready && !editing ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            <p>
              Payouts to <strong>{payout.bank_name}</strong> ••••{payout.account_last4}
              {payout.account_name ? ` (${payout.account_name})` : ""}
            </p>
            <p className="text-muted-foreground mt-1 text-xs">
              Your earnings are paid out to this account when you request a withdrawal and our team approves it. {commission}% platform commission is deducted from each client payment.
            </p>
            {payout.name_matches === false && (
              <p className="mt-1 text-xs text-amber-800" role="note">
                The holder name doesn&apos;t match the name on your verified ID{payout.verified_name ? ` (${payout.verified_name})` : ""}. Payouts to
                someone else&apos;s account are held for a check, so use an account in your own name.
              </p>
            )}
            {payout.locked && (
              <p className="text-muted-foreground mt-1 text-xs">A payout is on its way to this account, so you can change it once that payout is paid or refused.</p>
            )}
          </div>
          <Button size="sm" variant="outline" onClick={() => setEditing(true)} disabled={payout.locked}>Change</Button>
        </div>
      ) : (
        <PayoutForm
          current={payout}
          onDone={() => setEditing(false)}
          onCancel={payout?.ready ? () => setEditing(false) : undefined}
        />
      )}
    </section>
  );
}
