"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  JOBS_PAGE_SIZE,
  MY_REVIEWS_PAGE_SIZE,
  type JobGroup,
  useMarketAction,
  useMyJobs,
  useMyProvider,
  useMyProviderReviews,
  useRemoveProviderPhoto,
  useUploadProviderFile,
} from "@cn/core/api/providers";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AgentStatusBadge, EmptyState, ErrorState, LoadingState, formatDate, formatDateTime } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { formatBirr, priceBreakdown, priceRules, usePaymentsConfig, type JobPriceBody } from "@cn/core/api/payments";
import type { ClientRecord, Hire, MyProvider, NotReadyReason, Review } from "@cn/core/types/provider";
import { PhotoUploader } from "@/modules/marketplace/components/photo-uploader";
import { ProviderAvatar, verifiedLevel } from "@cn/ui/marketplace/provider-avatar";
import { ProviderForm, cleanForm, providerToForm } from "@/modules/marketplace/components/provider-form";
import { RatingSummary, StarInput, Stars, ScoreBadge, ScoreBreakdown, TypeBadge, VerificationBadges } from "@cn/ui/marketplace/trust";
import { TYPE_META } from "@cn/ui/marketplace/constants";
import { ContactActions } from "@/modules/marketplace/components/telegram-link";
import { PriceLine } from "@cn/ui/marketplace/payment-badge";
import { PayoutCard } from "@/modules/marketplace/components/payout-card";
import { EarningsPanel } from "@/modules/marketplace/components/earnings-panel";
import { ReviewItem } from "@/modules/marketplace/pages/provider-profile";
import { usePayoutPromptStore } from "@/store/payout-prompt-store";
import { autoCloseDate, hireStage, providerNext, STAGE_LABEL } from "@/lib/hire-stage";
import { HireTimeline } from "@/modules/marketplace/components/hire-timeline";
import { VettingChecklist } from "@/modules/marketplace/components/vetting-checklist";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "jobs", label: "Jobs" },
  { key: "vetting", label: "Documents" },
  { key: "earnings", label: "Earnings" },
  { key: "reviews", label: "Reviews" },
  { key: "profile", label: "Edit profile" },
  { key: "team", label: "Team" },
] as const;
type Tab = (typeof TABS)[number]["key"];
const asTab = (value: string | null): Tab | null => TABS.find((t) => t.key === value)?.key ?? null;

const LEGAL_PATHS: Record<string, string> = {
  terms: "/legal/terms",
  privacy: "/legal/privacy",
  marketplace_rules: "/legal/marketplace-rules",
  provider_agreement: "/legal/provider-agreement",
};

/** Listed or not, and for each reason a link to where it is fixed. */
function ReadinessBanner({ p, onOpen }: { p: MyProvider; onOpen: (t: Tab) => void }) {
  const r = p.readiness;
  if (!r || r.listed) return null;
  const neverListed = !p.approved_at;
  const fix = (x: NotReadyReason) => {
    const btn = "font-medium underline";
    if (x.fix === "profile") return <button type="button" className={btn} onClick={() => onOpen("profile")}>Edit profile</button>;
    if (x.fix === "vetting") return <button type="button" className={btn} onClick={() => onOpen("vetting")}>Open documents</button>;
    if (x.fix === "agreement") {
      const href = LEGAL_PATHS[x.key.replace("agreement:", "")] ?? "/legal";
      return <Link className={btn} href={href}>Read it</Link>;
    }
    return null;
  };
  return (
    <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950" role="status">
      <p className="font-semibold">
        {neverListed ? "You are not listed yet · ገና አልተዘረዘሩም" : "You are hidden from clients · ለደንበኞች አይታዩም"}
      </p>
      <p className="mt-1 text-xs">
        {neverListed
          ? "Clients can find and hire you once all of these are done:"
          : "Clients can't find or request you, and you can't accept new jobs, until you fix these. Jobs you already started can still be delivered and paid."}
      </p>
      <ul className="mt-2 space-y-1 text-xs">
        {r.reasons.map((x) => (
          <li key={x.key} className="flex flex-wrap items-baseline gap-x-2">
            <span aria-hidden="true">•</span>
            <span className="min-w-0">{x.label}</span>
            {fix(x)}
          </li>
        ))}
      </ul>
      {r.reasons.some((x) => x.fix === "agreement") && (
        <p className="mt-2 text-xs">To accept an updated document, reload this page: a window asks you to accept it.</p>
      )}
    </div>
  );
}

function Card({ title, children, className }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("border-border bg-card rounded-xl border p-5", className)}>
      {title && <h2 className="mb-3 text-sm font-semibold">{title}</h2>}
      {children}
    </section>
  );
}

function CompletenessRing({ percent, size = 64 }: { percent: number; size?: number }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Profile ${percent}% complete`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--muted)" strokeWidth="6" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={`${(percent / 100) * c} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="fill-foreground text-[13px] font-bold">
        {percent}%
      </text>
    </svg>
  );
}

function Overview({ p }: { p: MyProvider }) {
  const upload = useUploadProviderFile();
  const removePhoto = useRemoveProviderPhoto();
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title={p.entity_type === "company" ? "Company logo" : "Profile photo"} className="lg:col-span-2">
        <PhotoUploader
          name={p.display_name}
          entity={p.entity_type}
          verified={p.status === "approved" ? verifiedLevel(p) : null}
          currentUrl={p.photo_url}
          onSave={(file) => upload("photo", file)}
          onRemove={p.photo_url ? () => removePhoto() : undefined}
        />
      </Card>
      <PayoutCard className="lg:col-span-2" />
      <Card title="Profile completeness">
        <div className="flex items-center gap-4">
          <CompletenessRing percent={p.completeness.percent} />
          <p className="text-muted-foreground text-xs leading-relaxed">
            Complete profiles appear higher and get more requests. Finish the open items below.
          </p>
        </div>
        <ul className="mt-4 grid gap-1.5 text-xs sm:grid-cols-2">
          {p.completeness.items.map((i) => (
            <li key={i.key} className={i.done ? "text-primary" : "text-muted-foreground"}>
              {i.done ? "✓" : "○"} {i.label}
            </li>
          ))}
        </ul>
      </Card>
      <Card title={`Trust score ${p.trust_score}/100`}>
        <ScoreBreakdown parts={p.score_breakdown} />
        {p.tips.length > 0 && (
          <div className="bg-secondary/50 mt-4 rounded-lg p-3 text-xs">
            <p className="font-semibold">How to raise it</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {p.tips.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}

/** What the client pays and what the provider keeps for a price, worked out here from the same rules as the API. */
function PriceSplit({ job, amount }: { job: Hire; amount: number }) {
  const me = useMyProvider().data?.payload.provider;
  const config = usePaymentsConfig().data?.payload;
  const vatRegistered = me?.vat_registered ?? job.provider_vat_registered ?? false;
  const rules = priceRules(config, vatRegistered);
  const b = priceBreakdown(amount, rules);
  return (
    <p className="text-muted-foreground text-[11px]" aria-live="polite">
      Client pays <strong className="text-foreground tabular-nums">{formatBirr(b.clientPays)} ETB</strong>
      {b.vat > 0 ? ` (incl. ${formatBirr(b.vat)} VAT)` : ""} · you receive about{" "}
      <strong className="text-foreground tabular-nums">{formatBirr(b.providerGets)} ETB</strong> after the {rules.commissionPercent}% commission
      {b.commissionVat > 0 ? " and VAT on it" : ""}
      {b.vat > 0 ? "; the VAT is yours to file" : ""}.
    </p>
  );
}

/** Inline form for the price a provider names, on accept or later. */
function PriceForm({ job, mode, onDone, onCancel }: { job: Hire; mode: "accept" | "set_price"; onDone: () => void; onCancel: () => void }) {
  const { run, isPending } = useMarketAction<JobPriceBody>();
  const [price, setPrice] = useState(job.agreed_price != null ? String(job.agreed_price) : "");
  const [note, setNote] = useState(job.price_note ?? "");
  const [error, setError] = useState<string | null>(null);
  const amount = price.trim() ? Number(price) : null;
  const badAmount = amount != null && (!Number.isFinite(amount) || amount <= 0);
  const canSubmit = !badAmount && amount != null;

  return (
    <form
      className="bg-secondary/40 space-y-2 rounded-md p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!canSubmit) return;
        setError(null);
        const priceNote = note.trim() || undefined;
        try {
          await run(
            apiPaths.providers.myJob(job.id),
            MTD.POST,
            mode === "accept"
              ? { action: "accept", ...(amount != null ? { price: amount } : {}), price_note: priceNote }
              : { action: "set_price", price: amount as number, price_note: priceNote },
          );
          onDone();
        } catch (err) {
          setError(getErrorMessage(err));
        }
      }}
    >
      <p className="text-sm font-semibold">{mode === "accept" ? "Accept this job · ተቀበል" : "Your price · ዋጋ"}</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          type="number"
          inputMode="decimal"
          min={1}
          step="any"
          aria-label="Price in birr"
          placeholder="Price in birr"
          className="sm:w-44"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        />
        <Input placeholder="Note, e.g. includes stamp fees (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <p className="text-muted-foreground text-[11px]">
        {mode === "accept" ? "You can also set or change the price later, before the client pays." : "The client sees this price and can pay it online."}
      </p>
      {amount != null && !badAmount && <PriceSplit job={job} amount={amount} />}
      {badAmount && <p className="text-destructive text-xs">Enter a price above 0.</p>}
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={!canSubmit} loading={isPending}>{mode === "accept" ? "Accept job" : "Save price"}</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

/** A client's record, so the provider can judge a request before taking it. */
function ClientRecordLine({ record, name }: { record?: ClientRecord | null; name: string }) {
  if (!record) return null;
  const first = name.split(" ")[0];
  const parts: string[] = [];
  parts.push(record.hire_rate == null ? "New client" : `Hire rate ${record.hire_rate}%`);
  parts.push(`${record.paid_jobs} paid job${record.paid_jobs === 1 ? "" : "s"}`);
  if (record.cancelled_after_accept) parts.push(`${record.cancelled_after_accept} cancelled after acceptance`);
  if (record.left_unpaid) parts.push(`${record.left_unpaid} accepted but never paid`);
  return (
    <p className="text-muted-foreground text-xs" title="Hire rate: of the requests providers accepted, how many this client paid">
      <span className="text-foreground font-medium">{first}&apos;s record:</span> {parts.join(" · ")}
      {record.rating_count > 0 && (
        <span className="ml-1 inline-flex items-center gap-1">
          · <Stars value={record.rating_avg ?? 0} /> ({record.rating_count})
        </span>
      )}
    </p>
  );
}

function DeliverForm({ job, onDone }: { job: Hire; onDone: () => void }) {
  const { run, isPending } = useMarketAction<{ action: string; note: string }>();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="bg-secondary/40 space-y-2 rounded-md p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        try {
          await run(apiPaths.providers.myJob(job.id), MTD.POST, { action: "complete", note: note.trim() });
          onDone();
        } catch (err) {
          setError(getErrorMessage(err));
        }
      }}
    >
      <label htmlFor={`deliver-${job.id}`} className="text-sm font-semibold">What did you deliver? · ምን አስረከቡ?</label>
      <p className="text-muted-foreground text-xs">
        {job.client_name.split(" ")[0]} sees this and confirms. For example: &quot;Passport collected from the Bole office and handed over.&quot;
      </p>
      <Textarea id={`deliver-${job.id}`} rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button size="sm" type="submit" disabled={note.trim().length < 10} loading={isPending}>
          {job.agreed_price != null ? `Mark delivered and request ${job.agreed_price.toLocaleString("en")} ETB` : "Mark delivered"}
        </Button>
        <Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}

function RateClientForm({ job, onDone }: { job: Hire; onDone: () => void }) {
  const { run, isPending } = useMarketAction<{ rating: number; comment?: string }>();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const first = job.client_name.split(" ")[0];
  return (
    <div className="bg-secondary/40 space-y-2 rounded-md p-3">
      <p className="text-sm font-semibold">Rate {first} as a client · ደንበኛውን ይገምግሙ</p>
      <p className="text-muted-foreground text-xs">Clear instructions, paid on time, easy to reach? Other providers see this before taking {first}&apos;s requests. It is never public.</p>
      <StarInput value={rating} onChange={setRating} label={`Rating for ${first}`} />
      <Textarea rows={2} placeholder="Optional comment" value={comment} onChange={(e) => setComment(e.target.value)} />
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={!rating}
          loading={isPending}
          onClick={async () => {
            setError(null);
            try {
              await run(apiPaths.providers.rateClient(job.id), MTD.POST, { rating, comment: comment.trim() || undefined });
              onDone();
            } catch (err) {
              setError(getErrorMessage(err));
            }
          }}
        >
          Save rating
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </div>
  );
}

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

function Jobs() {
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

function ReplyBox({ review }: { review: Review }) {
  const { run, isPending } = useMarketAction<{ reply: string }>();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  if (review.reply) return null;
  return (
    <div className="mb-4 flex flex-col gap-2 sm:flex-row">
      <Textarea rows={2} placeholder="Public reply (once)" value={text} onChange={(e) => setText(e.target.value)} />
      <Button
        size="sm"
        disabled={text.trim().length < 2}
        loading={isPending}
        onClick={async () => {
          setError(null);
          try {
            await run(apiPaths.providers.reply(review.id), MTD.POST, { reply: text.trim() });
          } catch (err) {
            setError(getErrorMessage(err));
          }
        }}
      >
        Reply
      </Button>
      {error && <p className="text-destructive text-xs">{error}</p>}
    </div>
  );
}

function Reviews({ p }: { p: MyProvider }) {
  const [page, setPage] = useUrlPage();
  const { data, isLoading } = useMyProviderReviews(page);
  if (isLoading) return <LoadingState />;
  const items = data?.payload.items ?? [];
  return (
    <Card>
      <div className="mb-4"><RatingSummary value={p.rating_avg} count={p.rating_count} /></div>
      {!items.length ? (
        <p className="text-muted-foreground text-sm">No reviews yet. Clients can review you after a job is completed.</p>
      ) : (
        <ul>
          {items.map((r) => (
            <div key={r.id}>
              <ReviewItem review={r} providerName={p.display_name} providerPhoto={p.photo_url} providerEntity={p.entity_type} />
              <ReplyBox review={r} />
            </div>
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={MY_REVIEWS_PAGE_SIZE} total={data?.payload.total ?? 0} onPage={setPage} />
    </Card>
  );
}

function Team({ p }: { p: MyProvider }) {
  const { run, isPending } = useMarketAction<Record<string, string>>();
  const [slug, setSlug] = useState("");
  const [role, setRole] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const call = async (url: string, body: Record<string, string>, ok: string) => {
    setMsg(null);
    try {
      await run(url, MTD.POST, body);
      setMsg({ ok: true, text: ok });
      setSlug("");
    } catch (err) {
      setMsg({ ok: false, text: getErrorMessage(err) });
    }
  };
  const membership = (id: string, action: string) => call(apiPaths.providers.membership(id), { action }, "Updated.");

  if (p.provider_type === "agency") {
    return (
      <div className="space-y-4">
        <Card title="Team members">
          {!p.team?.length ? (
            <p className="text-muted-foreground text-sm">No members yet. Invite individual Guday Geday agents by their profile link.</p>
          ) : (
            <ul className="divide-border divide-y">
              {p.team.map((m) => (
                <li key={m.membership_id} className="flex flex-wrap items-center gap-3 py-3">
                  <ProviderAvatar name={m.display_name} photoUrl={m.photo_url} verified={m.id_verified ? "id" : null} size="sm" />
                  <span className="min-w-0 flex-1 text-sm">
                    <Link href={`/providers/${m.slug}`} className="font-medium hover:underline">{m.display_name}</Link>
                    <span className="text-muted-foreground block text-xs">
                      {m.status === "pending" ? (m.initiated_by === "member" ? "Asked to join" : "Invited, waiting for them") : m.role_title ?? "Member"}
                    </span>
                  </span>
                  {m.status === "pending" && m.initiated_by === "member" && (
                    <>
                      <Button size="sm" loading={isPending} onClick={() => membership(m.membership_id, "accept")}>Accept</Button>
                      <Button size="sm" variant="outline" onClick={() => membership(m.membership_id, "decline")}>Decline</Button>
                    </>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => membership(m.membership_id, "remove")}>Remove</Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Invite a member">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input placeholder="Their profile link name, e.g. meron-tadesse" value={slug} onChange={(e) => setSlug(e.target.value.replace(/^.*\/providers\//, ""))} />
            <Input placeholder="Role (optional)" value={role} onChange={(e) => setRole(e.target.value)} />
            <Button disabled={slug.trim().length < 3} loading={isPending}
              onClick={() => call(apiPaths.providers.invite, { member: slug.trim(), ...(role ? { role_title: role } : {}) }, "Invitation sent.")}>
              Invite
            </Button>
          </div>
          {msg && <p className={cn("mt-2 text-xs", msg.ok ? "text-primary" : "text-destructive")}>{msg.text}</p>}
        </Card>
      </div>
    );
  }

  return (
    <Card title="Agency">
      {p.agency ? (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span>
            {p.agency.status === "active" ? "Member of " : p.agency.initiated_by === "agency" ? "Invitation from " : "Request sent to "}
            <Link href={`/providers/${p.agency.slug}`} className="text-primary font-medium hover:underline">{p.agency.display_name}</Link>
          </span>
          {p.agency.status === "pending" && p.agency.initiated_by === "agency" && (
            <>
              <Button size="sm" loading={isPending} onClick={() => membership(p.agency!.membership_id, "accept")}>Accept</Button>
              <Button size="sm" variant="outline" onClick={() => membership(p.agency!.membership_id, "decline")}>Decline</Button>
            </>
          )}
          <Button size="sm" variant="ghost" onClick={() => membership(p.agency!.membership_id, "remove")}>
            {p.agency.status === "active" ? "Leave agency" : "Withdraw"}
          </Button>
        </div>
      ) : p.entity_type === "individual" ? (
        <>
          <p className="text-muted-foreground mb-3 text-sm">Work for an agency? Ask to join it. Your jobs and reviews will count towards the agency too.</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input placeholder="Agency profile link name, e.g. abay-clearing-forwarding-plc" value={slug} onChange={(e) => setSlug(e.target.value.replace(/^.*\/providers\//, ""))} />
            <Button disabled={slug.trim().length < 3} loading={isPending}
              onClick={() => call(apiPaths.providers.joinAgency, { agency: slug.trim() }, "Request sent. The agency will confirm.")}>
              Ask to join
            </Button>
          </div>
        </>
      ) : (
        <p className="text-muted-foreground text-sm">Companies list their own team as an agency.</p>
      )}
      {msg && <p className={cn("mt-2 text-xs", msg.ok ? "text-primary" : "text-destructive")}>{msg.text}</p>}
    </Card>
  );
}

const CHANGE_LABELS: Record<string, string> = {
  display_name: "your name",
  legal_name: "the legal name",
  tin: "the TIN",
  trade_license_no: "the trade licence number",
  vat_registered: "VAT registration",
  vat_number: "the VAT number",
};

function EditProfile({ p }: { p: MyProvider }) {
  const { run, isPending } = useMarketAction();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-4">
      <PayoutCard />
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

function QuickStats({ p, onOpen }: { p: MyProvider; onOpen: (t: Tab) => void }) {
  const counts = useMyJobs("new", 0).data?.payload.counts;
  const stats = [
    { label: "New requests", value: counts?.new ?? 0, tab: "jobs" as Tab, highlight: true },
    { label: "In progress", value: counts?.in_progress ?? 0, tab: "jobs" as Tab },
    { label: "Completed", value: counts?.completed ?? p.completed_count, tab: "jobs" as Tab },
    { label: "Rating", value: p.rating_count ? `${p.rating_avg.toFixed(1)} ★` : "New", tab: "reviews" as Tab },
  ];
  return (
    <dl className="border-border mt-5 grid grid-cols-2 gap-3 border-t pt-5 sm:grid-cols-4">
      {stats.map((s) => (
        <button
          key={s.label}
          type="button"
          onClick={() => onOpen(s.tab)}
          className={cn(
            "rounded-lg p-3 text-left transition-colors",
            s.highlight && typeof s.value === "number" && s.value > 0 ? "bg-gov-yellow/30 hover:bg-gov-yellow/40" : "bg-muted/60 hover:bg-muted",
          )}
        >
          <dt className="text-muted-foreground text-[11px] uppercase tracking-wide">{s.label}</dt>
          <dd className="text-gov-ink text-2xl font-bold tabular-nums">{s.value}</dd>
        </button>
      ))}
    </dl>
  );
}

export function MyProviderPage() {
  const gate = useAuthGate();
  const params = useSearchParams();
  const { data, isLoading, isError, error, refetch } = useMyProvider(gate === "ready");
  // The URL is the tab: notification links (?tab=earnings), Back and reloads all land on the right one
  const router = useRouter();
  const pathname = usePathname();
  const tab: Tab = asTab(params.get("tab")) ?? "overview";
  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params.toString());
    if (t === "overview") next.delete("tab");
    else next.set("tab", t);
    // Each tab pages its own list
    next.delete("page");
    next.delete("group");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const p = data?.payload.provider;

  return (
    <PageShell title="My provider profile · የእኔ መገለጫ" description="Your public profile, jobs, reviews and trust score.">
      {gate === "loading" || isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load your profile"} onRetry={() => refetch()} />
      ) : !p ? (
        <EmptyState title="You are not listed yet">
          <p className="mb-4">Join as a Guday Geday agent or agency to receive requests from clients.</p>
          <Link href="/providers/join"><Button>Join the marketplace</Button></Link>
        </EmptyState>
      ) : (
        <div className="space-y-6">
          {params.get("joined") && p.status === "pending" && (
            <p className="border-primary/40 bg-secondary/60 rounded-md border p-4 text-sm">
              Thanks! Your profile is waiting for staff review. Meanwhile, complete the items below to start with a higher trust score.
            </p>
          )}
          <section className="border-border bg-card rounded-xl border p-5 md:p-6">
            <div className="flex flex-col gap-5 md:flex-row md:items-center">
              <ProviderAvatar
                name={p.display_name}
                photoUrl={p.photo_url}
                entity={p.entity_type}
                verified={p.status === "approved" ? verifiedLevel(p) : null}
                size="lg"
              />
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-gov-ink text-xl font-bold">{p.display_name}</h2>
                  <AgentStatusBadge status={p.status} />
                  <TypeBadge type={p.provider_type} entity={p.entity_type} />
                </div>
                {p.headline && <p className="text-sm">{p.headline}</p>}
                <p className="text-muted-foreground text-xs">
                  {p.registration_no ? `${TYPE_META[p.provider_type].label} registration ${p.registration_no}` : "Registration number issued on approval"}
                  {p.license_expires_at ? ` · listing valid until ${formatDate(p.license_expires_at)}` : ""}
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <ScoreBadge score={p.trust_score} parts={p.score_breakdown} isNew={p.rating_count < 3} />
                  <RatingSummary value={p.rating_avg} count={p.rating_count} />
                  <VerificationBadges provider={p} />
                </div>
                {p.review_note && (p.status === "rejected" || p.status === "suspended") && (
                  <p className="text-destructive text-sm">Staff note: {p.review_note}{p.status === "rejected" ? " Edit your profile to resubmit." : ""}</p>
                )}
              </div>
              <div className="flex items-center gap-4">
                <button type="button" onClick={() => setTab("overview")} title="Profile completeness" className="shrink-0">
                  <CompletenessRing percent={p.completeness.percent} size={72} />
                </button>
                {(p.readiness ? p.readiness.listed : p.status === "approved") && (
                  <Link href={`/providers/${p.slug}`}><Button variant="outline">View public profile</Button></Link>
                )}
              </div>
            </div>
            <QuickStats p={p} onOpen={setTab} />
            {p.readiness ? (
              <ReadinessBanner p={p} onOpen={setTab} />
            ) : p.vetting && !p.vetting.complete && (
              <p className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                {p.status === "approved" ? "Some of your documents need attention to stay listed." : "Staff can approve your listing once your documents are verified."}{" "}
                <button type="button" className="font-medium underline" onClick={() => setTab("vetting")}>Open documents</button>
              </p>
            )}
          </section>

          <div role="tablist" className="border-border flex gap-1 overflow-x-auto overflow-y-hidden border-b [scrollbar-width:none]">
            {TABS.map((t) => (
              <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
                className={cn("-mb-px shrink-0 border-b-[3px] px-4 py-2.5 text-sm", tab === t.key ? "border-primary text-primary font-semibold" : "text-muted-foreground hover:text-foreground border-transparent")}>
                {t.label}
              </button>
            ))}
          </div>

          {tab === "overview" && <Overview p={p} />}
          {tab === "jobs" && <Jobs />}
          {tab === "vetting" && (p.vetting ? <VettingChecklist vetting={p.vetting} /> : <LoadingState />)}
          {tab === "earnings" && <EarningsPanel />}
          {tab === "reviews" && <Reviews p={p} />}
          {tab === "profile" && <EditProfile p={p} />}
          {tab === "team" && <Team p={p} />}
        </div>
      )}
    </PageShell>
  );
}
