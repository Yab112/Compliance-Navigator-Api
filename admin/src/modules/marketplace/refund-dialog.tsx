"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { formatETB, useRequestRefund } from "@cn/core/api/payments";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";

/** The payment being refunded. Works with a row from the payments list or a hire's payment. */
export type RefundTarget = {
  tx_ref: string;
  amount: number;
  refundable: number;
  gateway: string;
  title?: string | null;
  client_name?: string | null;
  provider_name?: string | null;
  unapplied_reason?: string | null;
};

/**
 * Ask for a refund of all or part of a payment. It is never carried out here: another staff member
 * approves it in Access, Approvals, and only then the money goes back. Reusable from the hire page.
 */
export function RefundForm({ payment, onClose }: { payment: RefundTarget; onClose: () => void }) {
  const id = useId();
  const { requestRefund, isPending } = useRequestRefund();
  const [amount, setAmount] = useState(String(payment.refundable));
  const [reason, setReason] = useState("");
  const [method, setMethod] = useState<"gateway" | "manual">("gateway");
  const [bank, setBank] = useState({ bank_name: "", account_name: "", account_number: "" });
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const value = Number(amount);
  const amountOk = Number.isFinite(value) && value > 0 && value <= payment.refundable;
  const bankOk = method === "gateway" || (bank.bank_name.trim().length > 1 && bank.account_name.trim().length > 1 && /^\d{6,20}$/.test(bank.account_number.replace(/\s/g, "")));
  const full = amountOk && Math.abs(value - payment.refundable) < 0.005;

  const submit = async () => {
    setError(null);
    try {
      const res = await requestRefund(payment.tx_ref, {
        amount: full ? undefined : value,
        reason: reason.trim(),
        method,
        client_bank: method === "manual" ? { ...bank, account_number: bank.account_number.replace(/\s/g, "") } : null,
      });
      if (res.approval) setDone("approval");
      else setDone("now");
    } catch (err) {
      setError(getErrorMessage(err, "Could not ask for this refund"));
    }
  };

  if (done) {
    return (
      <div className="bg-secondary/50 space-y-2 rounded-md p-3 text-sm" role="status">
        {done === "approval" ? (
          <p>
            Sent for approval. Another staff member with the Refund clients permission must approve it in{" "}
            <Link href="/access/approvals" className="text-primary hover:underline">Access, Approvals</Link>. Nothing is refunded until then.
          </p>
        ) : (
          <p>No other staff member could approve this, so it was carried out at once and recorded in the audit log.</p>
        )}
        <Button size="sm" variant="ghost" onClick={onClose}>Close</Button>
      </div>
    );
  }

  return (
    <form
      className="bg-secondary/50 space-y-3 rounded-md p-3 text-sm"
      aria-labelledby={`${id}-title`}
      onSubmit={(e) => {
        e.preventDefault();
        if (amountOk && reason.trim().length >= 5 && bankOk) void submit();
      }}
    >
      <p id={`${id}-title`} className="font-medium">
        Refund {payment.client_name ?? "the client"} for {payment.title ?? "this job"}
      </p>
      <p className="text-muted-foreground text-xs">
        Paid {formatETB(payment.amount)}. Up to {formatETB(payment.refundable)} can still be refunded.{" "}
        {payment.unapplied_reason
          ? "This extra payment was never credited to the provider, so nothing is taken back from them."
          : `The provider's share, our commission and the VAT on it are taken back in proportion. ${payment.provider_name ?? "The provider"}'s balance can go below zero; it is recovered from their next earnings.`}{" "}
        Chapa does not return its own fee.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`${id}-amount`} className="block text-xs font-medium">Amount to give back (ETB)</label>
          <Input
            id={`${id}-amount`}
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            aria-invalid={!amountOk}
            aria-describedby={`${id}-amount-hint`}
          />
          <p id={`${id}-amount-hint`} className={amountOk ? "text-muted-foreground text-[11px]" : "text-destructive text-[11px]"} aria-live="polite">
            {amountOk ? (full ? "Full refund" : "Part refund") : `Enter an amount above 0 and at most ${formatETB(payment.refundable)}`}
          </p>
        </div>
        <fieldset>
          <legend className="text-xs font-medium">How the money goes back</legend>
          <label className="mt-1 flex items-center gap-2 text-xs">
            <input type="radio" name={`${id}-method`} className="accent-primary" checked={method === "gateway"} onChange={() => setMethod("gateway")} />
            {payment.gateway === "simulated" ? "Test refund (no real money)" : "Through Chapa, to how the client paid"}
          </label>
          <label className="mt-1 flex items-center gap-2 text-xs">
            <input type="radio" name={`${id}-method`} className="accent-primary" checked={method === "manual"} onChange={() => setMethod("manual")} />
            We send it by bank transfer
          </label>
        </fieldset>
      </div>

      {method === "manual" && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor={`${id}-bank`} className="block text-xs font-medium">Client&apos;s bank</label>
            <Input id={`${id}-bank`} value={bank.bank_name} onChange={(e) => setBank({ ...bank, bank_name: e.target.value })} />
          </div>
          <div>
            <label htmlFor={`${id}-holder`} className="block text-xs font-medium">Account holder name</label>
            <Input id={`${id}-holder`} value={bank.account_name} onChange={(e) => setBank({ ...bank, account_name: e.target.value })} />
          </div>
          <div>
            <label htmlFor={`${id}-number`} className="block text-xs font-medium">Account number</label>
            <Input id={`${id}-number`} inputMode="numeric" autoComplete="off" value={bank.account_number} onChange={(e) => setBank({ ...bank, account_number: e.target.value })} />
          </div>
          <p className="text-muted-foreground text-[11px] sm:col-span-3">
            Stored encrypted. After approval, someone sends the transfer and confirms it here with the bank reference.
          </p>
        </div>
      )}

      <div>
        <label htmlFor={`${id}-reason`} className="block text-xs font-medium">Reason (shown to the client, the provider and the approver)</label>
        <Textarea id={`${id}-reason`} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" variant="destructive" loading={isPending} disabled={!amountOk || reason.trim().length < 5 || !bankOk}>
          Ask for approval
        </Button>
        <Button type="button" size="sm" variant="ghost" disabled={isPending} onClick={onClose}>Cancel</Button>
      </div>
      {error && <p className="text-destructive text-xs" role="alert">{error}</p>}
    </form>
  );
}
