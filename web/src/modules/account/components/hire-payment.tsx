"use client";

import Link from "next/link";
import { useState } from "react";
import { formatBirr, usePayHire, usePaymentsConfig } from "@cn/core/api/payments";
import { Button } from "@cn/ui/button";
import { getErrorMessage } from "@cn/core/lib/errors";
import { formatDate } from "@cn/ui/guday/shared";
import type { Hire } from "@cn/core/types/provider";
import { PriceLine } from "@cn/ui/marketplace/payment-badge";
import { hireStage } from "@/lib/hire-stage";

/** Price, payment state and the Pay button: you pay once the work is delivered. */
export function HirePayment({ hire }: { hire: Hire }) {
  const config = usePaymentsConfig();
  const { payHire, isPending } = usePayHire();
  const [error, setError] = useState<string | null>(null);
  const mode = config.data?.payload.mode;
  const stage = hireStage(hire);
  const pay = async (fallback: string) => {
    setError(null);
    try {
      await payHire(hire.id);
    } catch (err) {
      setError(getErrorMessage(err, fallback));
    }
  };

  const due = hire.amount_due ?? hire.agreed_price;
  const vat = hire.vat_due ?? 0;
  let action: React.ReactNode = null;
  if (stage === "paying") {
    // Left the checkout before finishing? The server hands back the same checkout, so nothing is paid twice
    action = (
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" size="sm" loading={isPending} onClick={() => pay("Could not reopen the payment")}>
          Continue payment
        </Button>
        <span className="text-muted-foreground text-[11px]">If you already paid, it will show as paid within a minute.</span>
      </div>
    );
  } else if (stage === "delivered" && mode && mode !== "off") {
    action = (
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-col items-start gap-1">
          <Button loading={isPending} disabled={config.isLoading} onClick={() => pay("Could not start the payment")}>
            Pay {formatBirr(due)} ETB
          </Button>
          {vat > 0 && <span className="text-muted-foreground text-[11px]">includes VAT {formatBirr(vat)} ETB</span>}
        </div>
        <span className="text-muted-foreground text-[11px]">
          {mode === "simulated" ? "Test mode: no real money moves." : "Secure checkout with Chapa: telebirr, CBE Birr, bank or card."}
        </span>
      </div>
    );
  } else if (hire.payment_status === "paid" && hire.paid_at) {
    action = (
      <p className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span>Paid through Compliance Navigator on {formatDate(hire.paid_at)}.</span>
        {hire.paid_tx_ref && (
          <Link
            href={`/receipts/payment/${encodeURIComponent(hire.paid_tx_ref)}`}
            className="text-primary font-medium hover:underline"
            aria-label={`Receipt for ${hire.title}`}
          >
            Receipt
          </Link>
        )}
      </p>
    );
  }

  return (
    <div className="mt-2 space-y-2">
      <PriceLine price={hire.agreed_price} note={hire.price_note} status={hire.payment_status} vat={vat} />
      {action}
      {error && <p className="text-destructive text-xs">{error}</p>}
    </div>
  );
}
