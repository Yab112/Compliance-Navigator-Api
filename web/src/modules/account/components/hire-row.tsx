"use client";

import Link from "next/link";
import { useState } from "react";
import { usePaymentsConfig } from "@cn/core/api/payments";
import { useMarketAction } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { formatDate } from "@cn/ui/guday/shared";
import { TYPE_META } from "@cn/ui/marketplace/constants";
import type { Hire } from "@cn/core/types/provider";
import { ProviderAvatar } from "@cn/ui/marketplace/provider-avatar";
import { ContactActions } from "@/modules/marketplace/components/telegram-link";
import { autoCloseDate, clientNext, hireStage, STAGE_LABEL } from "@/lib/hire-stage";
import { HireTimeline } from "@/modules/marketplace/components/hire-timeline";
import { ReviewForm, ReviewChangeForm, ClosedJobFeedback } from "@/modules/account/components/review-forms";
import { HirePayment } from "@/modules/account/components/hire-payment";

export function HireRow({ hire }: { hire: Hire }) {
  const { run, isPending } = useMarketAction<{ reason?: string }>();
  const [panel, setPanel] = useState<"review" | "dispute" | "change" | null>(null);
  const [reason, setReason] = useState("");
  const paymentsOn = usePaymentsConfig().data?.payload.enabled ?? false;
  const stage = hireStage(hire);
  // Only without online payment does a delivered job close on its own
  const closeBy = paymentsOn ? null : autoCloseDate(hire);
  const [error, setError] = useState<string | null>(null);
  const act = async (url: string, body?: { reason?: string }) => {
    setError(null);
    try {
      await run(url, MTD.POST, body);
      setPanel(null);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <li className="border-border bg-card rounded-md border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          {hire.provider_name && <ProviderAvatar name={hire.provider_name} photoUrl={hire.provider_photo_url} size="sm" />}
          <div className="min-w-0">
            <p className="font-medium">{hire.title}</p>
            <p className="text-muted-foreground text-xs">
              {hire.provider_name ? (
                <>
                  <Link href={`/providers/${hire.provider_slug}`} className="text-primary hover:underline">{hire.provider_name}</Link>
                  {hire.provider_type ? ` · ${TYPE_META[hire.provider_type].label}` : ""}
                </>
              ) : (
                "Staff are matching you with a provider"
              )}
              {" · "}requested {formatDate(hire.created_at)}
            </p>
          </div>
        </div>
        <span className="bg-secondary text-gov-ink shrink-0 rounded px-2 py-0.5 text-xs font-medium">{STAGE_LABEL[stage]}</span>
      </div>
      <HireTimeline stage={stage} next={clientNext(hire, stage, paymentsOn)} />
      {stage === "delivered" && hire.completion_note && (
        <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm">
          <p className="text-xs font-semibold text-emerald-900">{hire.provider_name?.split(" ")[0]} says it&apos;s done:</p>
          <p className="mt-1">{hire.completion_note}</p>
          {closeBy && <p className="text-muted-foreground mt-1 text-[11px]">Closes on its own on {formatDate(closeBy.toISOString())} unless you report a problem.</p>}
        </div>
      )}
      {hire.provider_name && ["requested", "accepted", "in_progress"].includes(hire.status) && (
        <div className="mt-3">
          <ContactActions
            name={hire.provider_name}
            phone={hire.provider_phone}
            telegram={hire.provider_telegram}
            shared={hire.contact_shared}
            pendingText={`${hire.provider_name}'s phone and Telegram appear here once they accept your request.`}
          />
        </div>
      )}
      {hire.status === "declined" && (
        <p className="mt-2 text-xs">
          <Link href={`/hire?type=${hire.provider_type ?? "guday_geday"}`} className="text-primary underline">Find someone else</Link>
        </p>
      )}
      {hire.disputed && (
        <p className="mt-2 text-xs">
          Problem reported: {hire.dispute_reason}.{" "}
          <span className="font-medium">
            {hire.dispute_status === "open" ? "Staff are looking into it." : hire.dispute_status === "upheld" ? "Staff upheld your complaint." : "Staff closed the complaint."}
          </span>
          {hire.dispute_note ? ` ${hire.dispute_note}` : ""}
        </p>
      )}
      <HirePayment hire={hire} />
      {(stage === "closed" || stage === "reviewed") && (
        <ClosedJobFeedback hire={hire} changing={panel === "change"} onRequestChange={() => setPanel("change")} />
      )}
      {error && <p className="text-destructive mt-2 text-xs">{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {/* Before paying you can walk away; after paying, problems go to our team (refunds included) */}
        {/* Until delivery you can walk away; after delivery you pay, or report a problem */}
        {["matching", "requested", "agree_price", "accepted", "in_progress"].includes(stage) && (
          <Button size="sm" variant="outline" loading={isPending} onClick={() => act(apiPaths.hires.cancel(hire.id))}>Cancel request</Button>
        )}
        {stage === "delivered" && !paymentsOn && (
          <Button size="sm" loading={isPending} onClick={() => act(apiPaths.hires.complete(hire.id))}>Confirm it&apos;s done</Button>
        )}
        {stage === "closed" && hire.provider_id && panel !== "review" && (
          <Button size="sm" onClick={() => setPanel("review")}>Leave a review</Button>
        )}
        {["accepted", "in_progress", "delivered"].includes(stage) && !hire.disputed && panel !== "dispute" && (
          <Button size="sm" variant="ghost" onClick={() => setPanel("dispute")}>Report a problem</Button>
        )}
      </div>
      {panel === "review" && <ReviewForm hire={hire} onDone={() => setPanel(null)} />}
      {panel === "change" && <ReviewChangeForm hire={hire} onDone={() => setPanel(null)} />}
      {panel === "dispute" && (
        <div className="bg-secondary/40 mt-3 space-y-2 rounded-md p-4">
          <p className="text-sm font-semibold">What went wrong?</p>
          <p className="text-muted-foreground text-xs">For example: asked for extra money, didn&apos;t show up, lost documents. Staff will contact both sides. Upheld complaints lower the provider&apos;s trust score.</p>
          <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="flex gap-2">
            <Button size="sm" variant="destructive" disabled={reason.trim().length < 5} loading={isPending}
              onClick={() => act(apiPaths.hires.dispute(hire.id), { reason: reason.trim() })}>
              Send report
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPanel(null)}>Cancel</Button>
          </div>
        </div>
      )}
    </li>
  );
}
