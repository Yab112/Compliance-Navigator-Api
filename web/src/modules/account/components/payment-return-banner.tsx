"use client";

import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { formatBirr, usePayment } from "@cn/core/api/payments";
import { cn } from "@cn/core/lib/utils";

const POLL_LIMIT_MS = 30 * 1000;

/** Banner after the gateway sends the client back with ?payment=<tx_ref>. Polls every 3 s for up to 30 s while pending. */
export function PaymentReturnBanner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [txRef, setTxRef] = useState<string | null>(() => params.get("payment"));
  const [timedOut, setTimedOut] = useState(false);
  const cleared = useRef(false);

  useEffect(() => {
    if (!txRef) return;
    const t = window.setTimeout(() => setTimedOut(true), POLL_LIMIT_MS);
    return () => window.clearTimeout(t);
  }, [txRef]);

  const { data, isError, error } = usePayment(txRef, !timedOut);
  const payment = data?.payload.payment;
  const settled = !!payment && payment.status !== "pending";
  const finished = settled || timedOut || isError;
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!finished || cleared.current || !params.get("payment")) return;
    cleared.current = true;
    const next = new URLSearchParams(params.toString());
    next.delete("payment");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    void queryClient.invalidateQueries({ queryKey: ["hires"] });
  }, [finished, params, pathname, router, queryClient]);

  if (!txRef) return null;
  const dismiss = (
    <button type="button" className="ml-auto text-xs underline" onClick={() => setTxRef(null)}>
      Dismiss
    </button>
  );

  let tone = "border-border bg-secondary/60";
  let body: React.ReactNode;
  if (isError) {
    tone = "border-destructive/40 bg-destructive/5";
    body = <span>We couldn&apos;t check this payment: {error?.message ?? "unknown error"}. Receipt {txRef}</span>;
  } else if (!payment || payment.status === "pending") {
    body = timedOut ? (
      <span>Your payment is still being confirmed. Check back in a few minutes; we update this page once the bank confirms. Receipt {txRef}</span>
    ) : (
      <span className="flex items-center gap-2">
        <span className="border-primary inline-block size-3 animate-spin rounded-full border-2 border-t-transparent" aria-hidden />
        Confirming your payment…
      </span>
    );
  } else if (payment.status === "success") {
    tone = "border-emerald-400 bg-emerald-50 text-emerald-950";
    body = (
      <span>
        Payment received: <strong>{formatBirr(payment.amount)} {payment.currency || "ETB"}</strong>.{" "}
        <Link href={`/receipts/payment/${encodeURIComponent(payment.tx_ref)}`} className="font-medium underline">
          View receipt
        </Link>
      </span>
    );
  } else {
    tone = "border-destructive/40 bg-destructive/5";
    body = <span>Payment didn&apos;t go through. Try again.</span>;
  }

  return (
    <div role="status" aria-live="polite" className={cn("mb-4 flex flex-wrap items-center gap-3 rounded-md border p-4 text-sm", tone)}>
      {body}
      {finished && dismiss}
    </div>
  );
}
