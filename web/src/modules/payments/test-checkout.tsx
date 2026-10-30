"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { formatBirr, useSimulatePayment, useTestCheckout } from "@cn/core/api/payments";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { getErrorMessage } from "@cn/core/lib/errors";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";

/** Stand-in for the Chapa checkout when payments run in "simulated" mode. */
export function TestCheckoutPage({ txRef }: { txRef: string }) {
  const gate = useAuthGate();
  const router = useRouter();
  const { data, isLoading, isError, error, refetch } = useTestCheckout(txRef, gate === "ready");
  const { simulate, isPending } = useSimulatePayment();
  const [choice, setChoice] = useState<"success" | "failed" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const checkout = data?.payload.checkout;
  const back = `/account/requests?payment=${encodeURIComponent(txRef)}`;

  const finish = async (outcome: "success" | "failed") => {
    setActionError(null);
    setChoice(outcome);
    try {
      await simulate(txRef, outcome);
      router.push(back);
    } catch (err) {
      setActionError(getErrorMessage(err, "Could not complete the test payment"));
      setChoice(null);
    }
  };

  return (
    <PageShell title="Test checkout · የሙከራ ክፍያ" description="For trying the hire payment flow with test payments only." maxWidth="md">
      {gate === "loading" || isLoading ? (
        <LoadingState />
      ) : isError ? (
        // A real (Chapa) payment is refused here for good, so there is nothing to retry
        <ErrorState
          message={getErrorMessage(error, "Could not load this checkout")}
          onRetry={/real payment/i.test(getErrorMessage(error, "")) ? undefined : () => refetch()}
        />
      ) : checkout ? (
        <>
          <div className="bg-gov-yellow/40 text-gov-ink border-gov-yellow mb-5 rounded-md border p-4 text-sm">
            <p className="font-semibold">This is a TEST checkout.</p>
            <p className="mt-1">No money moves. Online payments are running in test mode, so nothing is charged and nobody gets paid.</p>
          </div>
          <section className="border-border bg-card rounded-xl border p-5">
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-muted-foreground text-xs">Amount · መጠን</dt>
                <dd className="text-gov-ink text-3xl font-bold tabular-nums">
                  {formatBirr(checkout.amount)} {checkout.currency || "ETB"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs">Job · ሥራ</dt>
                <dd className="font-medium">{checkout.title}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs">Provider · አገልግሎት ሰጪ</dt>
                <dd className="font-medium">{checkout.provider_name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs">Reference</dt>
                <dd className="font-mono text-xs">{checkout.tx_ref}</dd>
              </div>
            </dl>
            {checkout.status !== "pending" ? (
              <div className="mt-5 text-sm">
                <p>This payment is already {checkout.status === "success" ? "paid" : checkout.status}.</p>
                <Link href={back} className="text-primary mt-2 inline-block font-medium hover:underline">Back to my hires</Link>
              </div>
            ) : (
              <div className="mt-5 flex flex-wrap items-center gap-4">
                <Button size="lg" loading={isPending && choice === "success"} disabled={isPending} onClick={() => finish("success")}>
                  Pay {formatBirr(checkout.amount)} {checkout.currency || "ETB"} (test)
                </Button>
                <Button variant="link" className="px-0" loading={isPending && choice === "failed"} disabled={isPending} onClick={() => finish("failed")}>
                  Make it fail
                </Button>
              </div>
            )}
            {actionError && <p className="text-destructive mt-3 text-xs">{actionError}</p>}
          </section>
        </>
      ) : null}
    </PageShell>
  );
}
