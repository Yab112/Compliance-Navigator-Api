"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  JOBS_PAGE_SIZE,
  type JobGroup,
  useMarketAction,
  useMyJobs,
  useMyProvider,
} from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { EmptyState, ErrorState, LoadingState, formatDateTime } from "@cn/ui/guday/shared";
import { usePaymentsConfig } from "@cn/core/api/payments";
import type { Hire } from "@cn/core/types/provider";
import { ProviderAvatar } from "@cn/ui/marketplace/provider-avatar";
import { Stars } from "@cn/ui/marketplace/trust";
import { ContactActions } from "@/modules/marketplace/components/telegram-link";
import { PriceLine } from "@cn/ui/marketplace/payment-badge";
import { usePayoutPromptStore } from "@/store/payout-prompt-store";
import { autoCloseDate, hireStage, providerNext, STAGE_LABEL } from "@/lib/hire-stage";
import { HireTimeline } from "@/modules/marketplace/components/hire-timeline";
import { Card } from "@/modules/marketplace/components/my-provider/shared";
import { PriceForm, ClientRecordLine, DeliverForm, RateClientForm } from "@/modules/marketplace/components/my-provider/job-forms";

function JobRow({ job }: { job: Hire }) {
  const { run, isPending } = useMarketAction<{ action: string; reason?: string }>();
  const [panel, setPanel] = useState<"decline" | "accept" | "price" | "deliver" | "rate" | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const paymentsOn = usePaymentsConfig().data?.payload.enabled ?? false;
  const showSetup = usePayoutPromptStore((s) => s.show);
  const myTelegram = useMyProvider().data?.payload.provider?.telegram_username;
  const stage = hireStage(job);
  const first = job.client_name.split(" ")[0];
  const live = ["requested", "agree_price", "accepted", "in_progress", "delivered", "paying"].includes(stage);
  const act = async (action: string, r?: string) => {
    setError(null);
    try {
      await run(apiPaths.providers.myJob(job.id), MTD.POST, { action, reason: r });
      setPanel(null);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  const closeBy = autoCloseDate(job);

  return (
    <li className="border-border space-y-2 border-t py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-3">
          <ProviderAvatar name={job.client_name} size="sm" />
          <span>
            <span className="block font-medium">{job.title}</span>
            <span className="text-muted-foreground block text-xs">
              {job.client_name} · {formatDateTime(job.created_at)}
              {job.sub_city ? ` · ${job.sub_city.replace(/_/g, " ")}` : ""}
              {job.delivery_mode === "client_office" ? " · at the client's office" : job.delivery_mode === "provider_office" ? " · at your office" : job.delivery_mode === "online" ? " · online" : ""}
            </span>
          </span>
        </span>
        <span className="bg-secondary text-gov-ink rounded px-2 py-0.5 text-xs font-medium">{STAGE_LABEL[stage]}</span>
      </div>
      <HireTimeline stage={stage} next={providerNext(job, stage, paymentsOn)} />

      {/* Deciding on a request: who is this client? */}
      {["requested", "agree_price", "accepted"].includes(stage) && (
        <ClientRecordLine record={job.client_record} name={job.client_name} />
      )}
      {live && (
        <ContactActions
          name={job.client_name}
          phone={job.client_phone}
          telegram={job.client_telegram}
          shared={job.contact_shared}
          pendingText={`Accept the job to see ${first}'s phone and Telegram.`}
        />
      )}
      {job.details && <p className="text-sm">{job.details}</p>}
      {job.agreed_price != null && <PriceLine price={job.agreed_price} note={job.price_note} status={job.payment_status} />}
      {job.payment_status === "paid" && job.paid_tx_ref && (
        <p className="text-xs">
          <Link
            href={`/receipts/statement/${encodeURIComponent(job.paid_tx_ref)}`}
            className="text-primary font-medium hover:underline"
            aria-label={`Statement for ${job.title}`}
          >
            Statement
          </Link>
        </p>
      )}
      {job.disputed && (
        <p className="text-destructive text-xs">
          {first} reported a problem: {job.dispute_reason}. {job.dispute_status === "open" ? "Our team will contact you." : `Staff decision: ${job.dispute_status}.`}
        </p>
      )}

      {stage === "delivered" && job.completion_note && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm">
          <p className="text-xs font-semibold text-emerald-900">You delivered:</p>
          <p className="mt-1">{job.completion_note}</p>
          {closeBy && <p className="text-muted-foreground mt-1 text-[11px]">Closes on its own on {formatDateTime(closeBy.toISOString())} unless {first} reports a problem.</p>}
        </div>
      )}

      {/* Closed: what the client said, and the provider's rating of the client */}
      {(stage === "closed" || stage === "reviewed") && (
        <div className="space-y-2">
          {job.review_rating ? (
            <div className="rounded-md border border-amber-200 bg-amber-50/60 p-3 text-sm">
              <p className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                {first}&apos;s review <Stars value={job.review_rating} />
                {job.review_edited_at && <span className="text-muted-foreground font-normal">edited</span>}
              </p>
              {job.review_comment && <p className="mt-1">&ldquo;{job.review_comment}&rdquo;</p>}
              {job.review_reply ? (
                <p className="text-muted-foreground mt-1 text-xs">Your reply: {job.review_reply}</p>
              ) : (
                <p className="text-muted-foreground mt-1 text-xs">You can reply once on the Reviews tab.</p>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground text-xs">{first} hasn&apos;t reviewed this job.</p>
          )}
          {job.client_rating ? (
            <p className="text-muted-foreground flex items-center gap-2 text-xs">
              You rated {first} <Stars value={job.client_rating} />
              {job.client_rating_comment ? `“${job.client_rating_comment}”` : ""}
            </p>
          ) : (
            panel !== "rate" && (
              <Button size="sm" variant="outline" onClick={() => setPanel("rate")}>Rate {first} as a client</Button>
            )
          )}
        </div>
      )}

      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex flex-wrap gap-2">
        {stage === "requested" && !panel && (
          <>
            <Button size="sm" onClick={() => setPanel("accept")}>Accept</Button>
            <Button size="sm" variant="outline" onClick={() => setPanel("decline")}>Decline</Button>
          </>
        )}
        {stage === "accepted" && <Button size="sm" loading={isPending} onClick={() => act("start")}>Start work</Button>}
        {/* The price can change until delivery; then it is what the client pays */}
        {["agree_price", "accepted", "in_progress"].includes(stage) && panel !== "price" && (
          <Button size="sm" variant={stage === "agree_price" ? "default" : "outline"} onClick={() => setPanel("price")}>
            {job.agreed_price != null ? "Change price" : "Set price"}
          </Button>
        )}
        {stage === "in_progress" && panel !== "deliver" && <Button size="sm" onClick={() => setPanel("deliver")}>Mark delivered</Button>}
      </div>

      {!myTelegram && live && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-sky-300 bg-sky-50 p-3">
          <p className="text-sm text-sky-950">
            <span className="font-semibold">Add your Telegram</span> so {first} can message you.
          </p>
          <Button size="sm" variant="outline" onClick={showSetup}>Add Telegram</Button>
        </div>
      )}

      {panel === "accept" && <PriceForm job={job} mode="accept" onDone={() => setPanel(null)} onCancel={() => setPanel(null)} />}
      {panel === "price" && <PriceForm job={job} mode="set_price" onDone={() => setPanel(null)} onCancel={() => setPanel(null)} />}
      {panel === "deliver" && <DeliverForm job={job} onDone={() => setPanel(null)} />}
      {panel === "rate" && <RateClientForm job={job} onDone={() => setPanel(null)} />}
      {panel === "decline" && (
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input placeholder="Reason the client will see" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button size="sm" variant="destructive" disabled={reason.trim().length < 3} loading={isPending} onClick={() => act("decline", reason.trim())}>
            Decline job
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setPanel(null)}>Cancel</Button>
        </div>
      )}
    </li>
  );
}

const JOB_TABS: { key: JobGroup; label: string }[] = [
  { key: "new", label: "New requests" },
  { key: "in_progress", label: "In progress" },
  { key: "completed", label: "Completed" },
  { key: "declined", label: "Declined or cancelled" },
];

const asJobGroup = (v: string | null): JobGroup | null => (JOB_TABS.some((t) => t.key === v) ? (v as JobGroup) : null);

export function Jobs() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [page, setPage] = useUrlPage();
  // Counts for every group come with any page; "new" page 0 is shared with QuickStats
  const probe = useMyJobs("new", 0);
  const probeCounts = probe.data?.payload.counts;
  // Until the provider picks a filter, open the first one that has jobs, not an empty "New requests"
  const picked = asJobGroup(params.get("group"));
  const group: JobGroup = picked ?? (probeCounts ? (JOB_TABS.find((t) => probeCounts[t.key] > 0) ?? JOB_TABS[0]).key : "new");
  const list = useMyJobs(group, page, !!probeCounts);
  const setGroup = (g: JobGroup) => {
    const next = new URLSearchParams(params.toString());
    next.set("group", g);
    next.delete("page");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  if (probe.isLoading || (list.isLoading && !list.data)) return <LoadingState />;
  if (probe.isError) return <ErrorState message={probe.error?.message ?? "Could not load jobs"} onRetry={() => probe.refetch()} />;
  if (list.isError) return <ErrorState message={list.error?.message ?? "Could not load jobs"} onRetry={() => list.refetch()} />;
  const counts = list.data?.payload.counts ?? probeCounts!;
  const totalJobs = JOB_TABS.reduce((sum, t) => sum + (counts[t.key] ?? 0), 0);
  if (!totalJobs) return <EmptyState title="No jobs yet">Requests from clients appear here. Complete your profile to show up higher.</EmptyState>;
  const shown = list.data?.payload.items ?? [];
  return (
    <Card>
      <div role="tablist" aria-label="Job status" className="mb-4 flex flex-wrap gap-1.5">
        {JOB_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={group === t.key}
            onClick={() => setGroup(t.key)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs",
              group === t.key ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary/50",
            )}
          >
            {t.label} <span className="tabular-nums opacity-80">({counts[t.key] ?? 0})</span>
          </button>
        ))}
      </div>
      {shown.length ? (
        <>
          <ul>{shown.map((j) => <JobRow key={j.id} job={j} />)}</ul>
          <Pager page={page} pageSize={JOBS_PAGE_SIZE} total={list.data?.payload.total ?? 0} onPage={setPage} />
        </>
      ) : (
        <p className="text-muted-foreground py-6 text-center text-sm">Nothing here.</p>
      )}
    </Card>
  );
}
