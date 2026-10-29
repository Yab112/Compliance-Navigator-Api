"use client";

import { useState } from "react";
import { useFaydaActions } from "@/api/guday";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/errors";
import { formatDate } from "@/modules/guday/components/shared";
import type { FaydaMode, IdVerification } from "@/types/guday";

export const FAYDA_RETURN_KEY = "cn-fayda-return";

export function VerifiedIdentityCard({ v }: { v: IdVerification }) {
  return (
    <div className="border-primary/40 bg-secondary/60 rounded-md border p-4">
      <p className="text-primary text-sm font-semibold">
        ✓ Identity verified with Fayda · በፋይዳ ተረጋግጧል
        {v.method === "fayda_sandbox" && (
          <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">TEST MODE</span>
        )}
      </p>
      <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground text-xs">Name</dt>
          <dd className="font-medium">{v.verified_name ?? "Not provided"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">National ID</dt>
          <dd className="font-mono">{v.masked_id}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">Verified</dt>
          <dd>{formatDate(v.verified_at)}</dd>
        </div>
      </dl>
    </div>
  );
}

export function VerifyStep({ mode }: { mode: FaydaMode }) {
  const { start, isPending } = useFaydaActions();
  const [error, setError] = useState<string | null>(null);

  return (
    <section className="border-border bg-card rounded-md border p-6">
      <h2 className="text-gov-ink text-xl font-bold">Verify your identity with Fayda</h2>
      <p className="text-muted-foreground text-sm">በፋይዳ ብሔራዊ መታወቂያ ማንነትዎን ያረጋግጡ</p>
      <p className="mt-4 text-sm leading-relaxed">
        Providers handle other people&apos;s documents, money and property, so every individual and every
        company representative verifies their national identity before a profile is reviewed. You will sign in on
        the Fayda (National ID Program) page and approve sharing your name with us.
      </p>
      <ul className="mt-4 space-y-1.5 text-sm">
        <li>• Have your Fayda number ready (12-digit FIN or the 16-digit number on your card).</li>
        <li>• Fayda sends a one-time code to the phone you registered with.</li>
        <li>• We keep only the last 4 digits of your ID number. One ID can verify only one account.</li>
      </ul>
      {mode === "sandbox" && (
        <p className="mt-4 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Test mode: the real Fayda service isn&apos;t connected yet. You&apos;ll see a test screen instead.
        </p>
      )}
      {error && <p className="text-destructive mt-4 text-sm">{error}</p>}
      <Button
        size="lg"
        className="mt-6"
        loading={isPending}
        onClick={async () => {
          setError(null);
          try {
            const url = await start();
            // Bring the user back to the same step after Fayda (see fayda-pages.tsx)
            try {
              sessionStorage.setItem(FAYDA_RETURN_KEY, window.location.pathname + window.location.search);
            } catch {}
            window.location.href = url;
          } catch (err) {
            setError(getErrorMessage(err, "Could not start Fayda verification"));
          }
        }}
      >
        Verify with Fayda · በፋይዳ ያረጋግጡ
      </Button>
    </section>
  );
}
