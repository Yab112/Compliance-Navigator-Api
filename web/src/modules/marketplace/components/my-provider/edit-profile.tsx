"use client";

import Link from "next/link";
import { useState } from "react";
import { useMarketAction } from "@cn/core/api/providers";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import type { MyProvider } from "@cn/core/types/provider";
import { ProviderForm, cleanForm, providerToForm } from "@/modules/marketplace/components/provider-form";
import { Card } from "@/modules/marketplace/components/my-provider/shared";

const CHANGE_LABELS: Record<string, string> = {
  display_name: "your name",
  legal_name: "the legal name",
  tin: "the TIN",
  trade_license_no: "the trade licence number",
  vat_registered: "VAT registration",
  vat_number: "the VAT number",
};

export function EditProfile({ p }: { p: MyProvider }) {
  const { run, isPending } = useMarketAction();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-4">
      {p.pending_change && (
        <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" role="status">
          Waiting for staff: your change to {Object.keys(p.pending_change.changes).map((k) => CHANGE_LABELS[k] ?? k).join(", ")}. Your profile shows
          the old details until it is approved.
        </p>
      )}
      {p.rejected_change && (
        <p className="text-destructive rounded-md border border-red-300 bg-red-50 p-3 text-sm" role="status">
          Your change to {Object.keys(p.rejected_change.changes).map((k) => CHANGE_LABELS[k] ?? k).join(", ")} was not accepted: {p.rejected_change.note}
        </p>
      )}
      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {saved ? <p className="text-primary text-sm">Saved ✓</p> : <p className="text-muted-foreground text-xs">Changes to your name, TIN, trade licence or VAT are checked by staff before they show.</p>}
          {p.status === "approved" && (
            <Link href={`/providers/${p.slug}`} target="_blank" className="text-primary text-xs font-semibold hover:underline">
              Preview public profile ↗
            </Link>
          )}
        </div>
        <ProviderForm
          mode="edit"
          providerType={p.provider_type}
          entityType={p.entity_type}
          lockedName={p.entity_type === "individual" && p.verified_name ? p.verified_name : null}
          initial={providerToForm(p)}
          initialServices={p.services ?? []}
          submitLabel="Save profile"
          isSubmitting={isPending}
          serverError={error}
          onSubmit={async (values) => {
            setError(null);
            setSaved(false);
            try {
              await run(apiPaths.providers.me, MTD.PATCH, cleanForm(values));
              setSaved(true);
              window.scrollTo({ top: 0, behavior: "smooth" });
            } catch (err) {
              setError(getErrorMessage(err, "Could not save"));
            }
          }}
        />
      </Card>
    </div>
  );
}
