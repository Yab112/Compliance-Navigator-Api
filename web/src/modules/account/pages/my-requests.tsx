"use client";

import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { formatBirr, usePayHire, usePayment, usePaymentsConfig } from "@/api/payments";
import { HIRES_PAGE_SIZE, useMarketAction, useMyClientRecord, useMyHires } from "@/api/providers";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@/components/ui/button";
import { Pager, useUrlPage } from "@/components/ui/pager";
import { Textarea } from "@/components/ui/textarea";
import { apiPaths } from "@/lib/constants/api-paths";
import { MTD } from "@/lib/constants/methods";
import { getErrorMessage } from "@/lib/errors";
import { EmptyState, ErrorState, LoadingState, formatDate } from "@/modules/guday/components/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { StarInput, Stars } from "@/modules/marketplace/components/trust";
import { SUB_RATINGS, TYPE_META } from "@/modules/marketplace/constants";
import type { ClientRecord, Hire, ReviewInput } from "@/types/provider";
import { ProviderAvatar } from "@/modules/marketplace/components/provider-avatar";
import { ContactActions } from "@/modules/marketplace/components/telegram-link";
import { PriceLine } from "@/modules/marketplace/components/payment-badge";
import { cn } from "@/lib/utils";
import { autoCloseDate, clientNext, hireStage, STAGE_LABEL } from "@/lib/hire-stage";
import { HireTimeline } from "@/modules/marketplace/components/hire-timeline";

function ReviewForm({ hire, onDone }: { hire: Hire; onDone: () => void }) {
  const { run, isPending } = useMarketAction<ReviewInput>();
  const [rating, setRating] = useState(0);
  const [subs, setSubs] = useState<Record<string, number>>({});
  const [again, setAgain] = useState<boolean | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="bg-secondary/40 mt-3 space-y-3 rounded-md p-4">
      <p className="text-sm font-semibold">Review {hire.provider_name} · ግምገማ</p>
      <div className="flex items-center gap-3">
        <span className="w-28 text-xs font-medium">Overall</span>
        <StarInput value={rating} onChange={setRating} label="Overall rating" />
      </div>
      {SUB_RATINGS.map((s) => (
        <div key={s.key} className="flex items-center gap-3">
          <span className="w-28 text-xs">{s.label}</span>
          <StarInput size="sm" value={subs[s.key] ?? 0} onChange={(v) => setSubs((x) => ({ ...x, [s.key]: v }))} label={s.label} />
        </div>
      ))}
      <fieldset className="flex items-center gap-4 text-xs">
        <legend className="sr-only">Would you hire again?</legend>
        <span className="w-28 font-medium">Hire again?</span>
        {[{ v: true, l: "Yes" }, { v: false, l: "No" }].map((o) => (
          <label key={o.l} className="flex items-center gap-1.5">
            <input type="radio" name={`again-${hire.id}`} className="accent-primary" checked={again === o.v} onChange={() => setAgain(o.v)} />
            {o.l}
          </label>
        ))}
      </fieldset>
      <Textarea rows={3} placeholder="What went well, what didn't? Your first name and initial are shown." value={comment} onChange={(e) => setComment(e.target.value)} />
      {error && <p className="text-destructive text-xs">{error}</p>}
      <Button
        size="sm"
        disabled={!rating}
        loading={isPending}
        onClick={async () => {
          setError(null);
          try {
            await run(apiPaths.hires.review(hire.id), MTD.POST, {
              rating,
              ...subs,
              would_hire_again: again ?? undefined,
              comment: comment.trim() || undefined,
            });
            onDone();
          } catch (err) {
            setError(getErrorMessage(err, "Could not save your review"));
          }
        }}
      >
        Publish review
      </Button>
    </div>
  );
}

type ChangeBody = { rating: number; comment?: string; reason: string };

/** Ask to change a published review. Staff approve it before it appears; nothing changes until then. */
function ReviewChangeForm({ hire, onDone }: { hire: Hire; onDone: () => void }) {
  const { run, isPending } = useMarketAction<ChangeBody>();
  const [rating, setRating] = useState(hire.review_rating ?? 0);
  const [comment, setComment] = useState(hire.review_comment ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const unchanged = rating === (hire.review_rating ?? 0) && comment.trim() === (hire.review_comment ?? "").trim();
  const commentId = `change-comment-${hire.id}`;
  const reasonId = `change-reason-${hire.id}`;

  return (
    <div className="bg-secondary/40 mt-3 space-y-3 rounded-md p-4">
      <div>
        <p className="text-sm font-semibold">Request a change to your review</p>
        <p className="text-muted-foreground text-xs">Our team reviews changes before they appear. Until then your review stays as it is.</p>
      </div>
      <div className="flex items-center gap-3">
        <span className="w-28 text-xs font-medium">Rating</span>
        <StarInput value={rating} onChange={setRating} label="New rating" />
      </div>
      <div className="space-y-1">
        <label htmlFor={commentId} className="text-xs font-medium">Comment</label>
        <Textarea id={commentId} rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
      </div>
      <div className="space-y-1">
        <label htmlFor={reasonId} className="text-xs font-medium">Why do you want to change it?</label>
        <Textarea id={reasonId} rows={2} placeholder="For example: the provider fixed the problem afterwards." value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      {unchanged && rating > 0 && <p className="text-muted-foreground text-xs">Change the rating or the comment to send a request.</p>}
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={!rating || unchanged || reason.trim().length < 5}
          loading={isPending}
          onClick={async () => {
            setError(null);
            try {
              await run(apiPaths.hires.reviewChange(hire.id), MTD.POST, {
                rating,
                comment: comment.trim() || undefined,
                reason: reason.trim(),
              });
              onDone();
            } catch (err) {
              setError(getErrorMessage(err, "Could not send your request"));
            }
          }}
        >
          Send for review
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </div>
  );
}

/** On closed jobs: how the provider rated the client, and the client's own review with its reply. */
function ClosedJobFeedback({ hire, changing, onRequestChange }: { hire: Hire; changing: boolean; onRequestChange: () => void }) {
  const who = hire.provider_name?.split(" ")[0] ?? "The provider";
  if (!hire.client_rating && !hire.review_rating) return null;
  return (
    <div className="mt-3 space-y-3 text-sm">
      {hire.client_rating ? (
        <div>
          <p className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="font-medium">{who} rated you</span>
            <Stars value={hire.client_rating} />
          </p>
          {hire.client_rating_comment && <p className="text-muted-foreground mt-0.5 text-xs">&ldquo;{hire.client_rating_comment}&rdquo;</p>}
        </div>
      ) : null}
      {hire.review_rating ? (
        <div className="border-border rounded-md border p-3">
          <p className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="font-medium">Your review</span>
            <Stars value={hire.review_rating} />
            {hire.review_edited_at && <span className="text-muted-foreground">· edited</span>}
          </p>
          {hire.review_comment && <p className="mt-1 text-sm">{hire.review_comment}</p>}
          {hire.review_reply && (
            <div className="border-primary/40 mt-2 border-l-2 pl-3 text-xs">
              <p className="font-medium">{who} replied</p>
              <p className="text-muted-foreground mt-0.5">{hire.review_reply}</p>
            </div>
          )}
          {hire.review_change_status === "pending" ? (
            <p className="text-muted-foreground mt-2 text-xs">Change requested · waiting for our team</p>
          ) : (
            <>
              {/* A rejection isn't final: new facts (e.g. the document arrived after all) can justify a new request */}
              {hire.review_change_status === "rejected" && (
                <p className="text-muted-foreground mt-2 text-xs">Your last change request was not approved.</p>
              )}
              {!changing && (
                <Button size="sm" variant="ghost" className="mt-2 -ml-2" onClick={onRequestChange}>
                  Request a change
                </Button>
              )}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

/** Price, payment state and the Pay button: you pay once the work is delivered. */
function HirePayment({ hire }: { hire: Hire }) {
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

function HireRow({ hire }: { hire: Hire }) {
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

const POLL_LIMIT_MS = 30 * 1000;

/** Banner after the gateway sends the client back with ?payment=<tx_ref>. Polls every 3 s for up to 30 s while pending. */
function PaymentReturnBanner() {
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

type Tab = "active" | "history";

/** What providers see about this client when a request arrives. */
function ClientRecordCard({ record }: { record: ClientRecord }) {
  const items: { label: string; value: React.ReactNode; hint?: string }[] = [
    { label: "Paid jobs", value: record.paid_jobs },
    record.hire_rate == null
      ? { label: "Hire rate", value: "New client", hint: "shown after 3 decided requests" }
      : { label: "Hire rate", value: `${record.hire_rate}%` },
    { label: "Cancelled after acceptance", value: record.cancelled_after_accept },
    {
      label: "Rating from providers",
      value: record.rating_count && record.rating_avg != null ? (
        <span className="inline-flex items-center gap-1">
          <Stars value={record.rating_avg} />
          <span className="text-muted-foreground text-xs font-normal">({record.rating_count})</span>
        </span>
      ) : (
        "No ratings yet"
      ),
    },
  ];
  if (record.member_since) items.push({ label: "Member since", value: formatDate(record.member_since) });

  return (
    <section aria-labelledby="client-record-title" className="border-border bg-card mb-5 rounded-md border p-4">
      <h2 id="client-record-title" className="text-sm font-semibold">
        Your record <span className="text-muted-foreground font-normal">· as providers see it</span>
      </h2>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-5">
        {items.map((i) => (
          <div key={i.label} className="min-w-0">
            <dt className="text-muted-foreground text-[11px]">{i.label}</dt>
            <dd className="text-sm font-semibold tabular-nums">{i.value}</dd>
            {i.hint && <dd className="text-muted-foreground text-[11px]">{i.hint}</dd>}
          </div>
        ))}
      </dl>
      <p className="text-muted-foreground mt-3 text-[11px]">
        Hire rate: of the requests providers accepted, how many you paid. Only providers you send a request to see this.
      </p>
    </section>
  );
}

export function MyRequests() {
  const gate = useAuthGate();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: Tab = params.get("tab") === "history" ? "history" : "active";
  const [page, setPage] = useUrlPage();
  const { data, isLoading, isError, error, refetch } = useMyHires(tab, page, gate === "ready");
  const result = data?.payload;
  const shown = result?.items ?? [];
  const counts = result?.counts ?? { active: 0, history: 0 };
  const record = useMyClientRecord(gate === "ready").data?.payload.record;
  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params.toString());
    if (t === "history") next.set("tab", "history");
    else next.delete("tab");
    next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "active", label: "Active", count: counts.active },
    { key: "history", label: "History", count: counts.history },
  ];

  return (
    <PageShell
      title="My hires · የቀጠርኳቸው"
      description="Everyone you hired through the marketplace. You pay once the work is delivered, then leave a review so others know whom they are hiring."
      maxWidth="lg"
    >
      {gate === "ready" && <PaymentReturnBanner />}
      {gate === "loading" || isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load your hires"} onRetry={() => refetch()} />
      ) : counts.active + counts.history === 0 ? (
        <EmptyState title="No hires yet">
          <p className="mb-4">Find a verified Guday Geday agent or agency.</p>
          <Link href="/hire"><Button>Browse providers</Button></Link>
        </EmptyState>
      ) : (
        <>
          {record && <ClientRecordCard record={record} />}
          <div role="tablist" aria-label="My hires" className="border-border mb-4 flex gap-1 border-b">
            {tabs.map((t) => (
              <button
                key={t.key}
                type="button"
                role="tab"
                id={`hires-tab-${t.key}`}
                aria-selected={tab === t.key}
                aria-controls="hires-panel"
                onClick={() => setTab(t.key)}
                className={cn(
                  "-mb-px border-b-2 px-3 py-2 text-sm",
                  tab === t.key ? "border-primary text-primary font-semibold" : "text-muted-foreground hover:text-foreground border-transparent",
                )}
              >
                {t.label} <span className="tabular-nums">({t.count})</span>
              </button>
            ))}
          </div>
          <div id="hires-panel" role="tabpanel" aria-labelledby={`hires-tab-${tab}`}>
            {shown.length === 0 ? (
              tab === "active" ? (
                <EmptyState title="No active hires">
                  <p className="mb-4">Requests you send and jobs in progress appear here.</p>
                  <Link href="/hire"><Button>Browse providers</Button></Link>
                </EmptyState>
              ) : (
                <EmptyState title="No history yet">
                  <p>Closed, declined and cancelled requests appear here.</p>
                </EmptyState>
              )
            ) : (
              <>
                <ul className="space-y-3">
                  {shown.map((h) => (
                    <HireRow key={h.id} hire={h} />
                  ))}
                </ul>
                <Pager page={page} pageSize={HIRES_PAGE_SIZE} total={result?.total ?? 0} onPage={setPage} />
              </>
            )}
          </div>
        </>
      )}
      <p className="text-muted-foreground mt-6 text-sm">
        Problem with a hire that the provider can&apos;t fix?{" "}
        <Link href="/account/support" className="text-primary font-medium hover:underline">
          Write to our support team
        </Link>
        .
      </p>
    </PageShell>
  );
}
