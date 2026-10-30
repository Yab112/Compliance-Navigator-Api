"use client";

import Link from "next/link";
import { Input } from "@cn/ui/input";
import { Field } from "@cn/ui/guday/shared";
import { type Completeness } from "@cn/core/types/organizations";
import { CompletenessMeter } from "@cn/ui/organizations/shared";

export function ReviewSection({
  completeness,
  isLive,
  status,
  change,
  setChange,
  liveUrl,
}: {
  completeness: Completeness;
  isLive: boolean;
  status?: string;
  change: { change_summary: string; change_reason: string; effective_at: string };
  setChange: (c: { change_summary: string; change_reason: string; effective_at: string }) => void;
  liveUrl: string | null;
}) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div className="space-y-5">
      <CompletenessMeter completeness={completeness} />
      {completeness.core_missing.length > 0 && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
          You can save and submit now, but the platform team can only publish once the items marked ▲ are filled in.
        </p>
      )}
      {isLive ? (
        <div className="border-border space-y-3 rounded-md border p-4">
          <p className="text-sm font-semibold">This service is live. Tell us about the change · ለውጡን ይንገሩን</p>
          <p className="text-muted-foreground text-sm">
            People following this service on their paths get a notification. The current version stays public until the change takes effect.
          </p>
          <Field label="What changed" htmlFor="ch-summary" required hint="e.g. The fee rises from 302 to 350 ETB">
            <Input id="ch-summary" value={change.change_summary} onChange={(e) => setChange({ ...change, change_summary: e.target.value })} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Effective from" htmlFor="ch-date" hint="Leave empty for as soon as it's approved">
              <Input id="ch-date" type="date" min={today} value={change.effective_at} onChange={(e) => setChange({ ...change, effective_at: e.target.value })} />
            </Field>
            <Field label="Reason or legal reference" htmlFor="ch-reason">
              <Input id="ch-reason" value={change.change_reason} onChange={(e) => setChange({ ...change, change_reason: e.target.value })} placeholder="e.g. Directive 12/2026" />
            </Field>
          </div>
        </div>
      ) : (
        <p className="text-sm">
          When you submit, the platform team checks the service and publishes it. It then appears on every path that needs it.
        </p>
      )}
      {status === "scheduled" && <p className="text-sm text-sky-900">An approved change is waiting for its effective date.</p>}
      {liveUrl && (
        <Link href={liveUrl} className="text-primary text-sm hover:underline">
          View the live version ↗
        </Link>
      )}
    </div>
  );
}
