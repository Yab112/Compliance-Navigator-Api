"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMyJobs, useMyProvider } from "@cn/core/api/providers";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { cn } from "@cn/core/lib/utils";
import { AgentStatusBadge, EmptyState, ErrorState, LoadingState, formatDate } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import type { MyProvider, NotReadyReason } from "@cn/core/types/provider";
import { ProviderAvatar, verifiedLevel } from "@cn/ui/marketplace/provider-avatar";
import { RatingSummary, ScoreBadge, TypeBadge, VerificationBadges } from "@cn/ui/marketplace/trust";
import { TYPE_META } from "@cn/ui/marketplace/constants";
import { EarningsPanel } from "@/modules/marketplace/components/earnings-panel";
import { VettingChecklist } from "@/modules/marketplace/components/vetting-checklist";
import { CompletenessRing } from "@/modules/marketplace/components/my-provider/shared";
import { Overview } from "@/modules/marketplace/components/my-provider/overview";
import { Jobs } from "@/modules/marketplace/components/my-provider/jobs";
import { Reviews } from "@/modules/marketplace/components/my-provider/reviews";
import { Team } from "@/modules/marketplace/components/my-provider/team";
import { EditProfile } from "@/modules/marketplace/components/my-provider/edit-profile";

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
