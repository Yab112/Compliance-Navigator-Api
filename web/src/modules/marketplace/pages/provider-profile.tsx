"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Calendar03Icon,
  Clock01Icon,
  Link01Icon,
  Location01Icon,
  TranslateIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useProvider, useProviderReviews, type ReviewSort } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { cn } from "@cn/core/lib/utils";
import { ErrorState, LoadingState, formatDate, languageLabel } from "@cn/ui/guday/shared";
import type { ProviderProfileView, Review } from "@cn/core/types/provider";
import { HireForm } from "@/modules/marketplace/components/hire-form";
import { ProviderAvatar, verifiedLevel } from "@cn/ui/marketplace/provider-avatar";
import { ScoreBadge, ScoreBreakdown, Stars, TypeBadge, VerificationBadges } from "@cn/ui/marketplace/trust";
import { DELIVERY_LABELS, SUB_RATINGS, areaLabel, formatFee, memberSince, responseLabel, specialtyLabel } from "@cn/ui/marketplace/constants";
import { PageNav } from "@cn/ui/layout/page-nav";

function Section({ id, title, am, children, aside }: { id?: string; title: string; am?: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section id={id} className="border-border bg-card scroll-mt-28 rounded-xl border p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-gov-ink text-lg font-semibold">
          {title} {am && <span className="text-muted-foreground text-sm font-normal">· {am}</span>}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

function Bar({ value, max = 1, className }: { value: number; max?: number; className?: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <span className={cn("bg-muted block h-2 overflow-hidden rounded-full", className)} aria-hidden>
      <span className="bg-primary block h-full rounded-full" style={{ width: `${pct}%` }} />
    </span>
  );
}

export function ReviewItem({ review, providerName, providerPhoto, providerEntity }: {
  review: Review;
  providerName?: string;
  providerPhoto?: string | null;
  providerEntity?: ProviderProfileView["entity_type"];
}) {
  const subs = SUB_RATINGS.filter((s) => review[s.key] != null);
  return (
    <li className="border-border border-t py-5 first:border-t-0 first:pt-0">
      <div className="flex items-start gap-3">
        <ProviderAvatar name={review.client_name} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold">{review.client_name}</p>
            <span className="text-muted-foreground text-xs">{formatDate(review.created_at)}</span>
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs">
            <Stars value={review.rating} />
            <span className="text-muted-foreground">{review.job_title ?? review.service_name ?? "Job"}</span>
            {review.paid_through_platform && (
              <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-900">
                ✓ Paid through Compliance Navigator
              </span>
            )}
          </div>
          {review.comment && <p className="mt-2 text-sm leading-relaxed">{review.comment}</p>}
          {(subs.length > 0 || review.would_hire_again != null) && (
            <p className="text-muted-foreground mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
              {subs.map((s) => (
                <span key={s.key}>
                  {s.label} <strong className="text-foreground">{review[s.key]}</strong>/5
                </span>
              ))}
              {review.would_hire_again != null && (
                <span className={review.would_hire_again ? "text-primary font-medium" : ""}>
                  {review.would_hire_again ? "✓ Would hire again" : "Would not hire again"}
                </span>
              )}
            </p>
          )}
          {review.reply && (
            <div className="bg-secondary/60 mt-3 flex gap-2.5 rounded-lg p-3">
              {providerName && <ProviderAvatar name={providerName} photoUrl={providerPhoto} entity={providerEntity} size="xs" />}
              <div className="text-xs">
                <p className="font-semibold">Reply from {providerName ?? "the provider"}</p>
                <p className="mt-0.5 leading-relaxed">{review.reply}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

function Reviews({ provider: p }: { provider: ProviderProfileView }) {
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState<ReviewSort>("recent");
  const custom = offset > 0 || sort !== "recent";
  const query = useProviderReviews(p.slug, offset, custom, sort);
  const page = custom ? query.data?.payload : p.reviews;
  const rb = p.rating_breakdown;
  const dist = p.rating_distribution ?? {};
  const most = Math.max(1, ...Object.values(dist));

  return (
    <Section
      id="reviews"
      title={`Reviews (${p.reviews.total})`}
      am="ግምገማዎች"
      aside={
        p.reviews.total > 1 ? (
          <label className="text-xs">
            <span className="sr-only">Sort reviews</span>
            <select
              value={sort}
              onChange={(e) => {
                setSort(e.target.value as ReviewSort);
                setOffset(0);
              }}
              className="border-border bg-card h-8 rounded-md border px-2"
            >
              <option value="recent">Most recent</option>
              <option value="highest">Highest rated</option>
              <option value="lowest">Lowest rated</option>
            </select>
          </label>
        ) : null
      }
    >
      <p className="text-muted-foreground -mt-2 mb-5 text-xs">
        Only clients who hired {p.display_name} through the platform and finished the job can leave a review.
      </p>
      {p.rating_count > 0 && (
        <div className="bg-secondary/40 mb-6 grid gap-6 rounded-xl p-5 md:grid-cols-[140px_1fr_1fr]">
          <div className="text-center">
            <p className="text-gov-ink text-5xl font-bold">{p.rating_avg.toFixed(1)}</p>
            <Stars value={p.rating_avg} className="text-lg" />
            <p className="text-muted-foreground text-xs">{p.rating_count} reviews</p>
          </div>
          <ul className="space-y-1.5 text-xs" aria-label="Rating distribution">
            {["5", "4", "3", "2", "1"].map((star) => (
              <li key={star} className="grid grid-cols-[2.5rem_1fr_1.5rem] items-center gap-2">
                <span>{star} ★</span>
                <Bar value={dist[star] ?? 0} max={most} />
                <span className="text-muted-foreground text-right tabular-nums">{dist[star] ?? 0}</span>
              </li>
            ))}
          </ul>
          <dl className="space-y-2 text-xs">
            {SUB_RATINGS.map((s) => (
              <div key={s.key}>
                <div className="flex justify-between">
                  <dt>{s.label}</dt>
                  <dd className="font-semibold tabular-nums">{rb[s.key] != null ? rb[s.key]!.toFixed(1) : "-"}</dd>
                </div>
                <Bar value={rb[s.key] ?? 0} max={5} className="mt-1 h-1.5" />
              </div>
            ))}
            {rb.would_hire_again != null && (
              <p className="text-primary pt-1 font-semibold">{Math.round(rb.would_hire_again * 100)}% would hire again</p>
            )}
          </dl>
        </div>
      )}
      {custom && query.isLoading ? (
        <LoadingState />
      ) : !page?.items.length ? (
        <p className="text-muted-foreground text-sm">No reviews yet. New providers start with a neutral rating.</p>
      ) : (
        <ul>
          {page.items.map((r) => (
            <ReviewItem key={r.id} review={r} providerName={p.display_name} providerPhoto={p.photo_url} providerEntity={p.entity_type} />
          ))}
        </ul>
      )}
      {p.reviews.total > 10 && (
        <div className="mt-5 flex justify-center gap-2">
          <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - 10))}>
            Previous
          </Button>
          <Button size="sm" variant="outline" disabled={offset + 10 >= p.reviews.total} onClick={() => setOffset((o) => o + 10)}>
            More reviews
          </Button>
        </div>
      )}
    </Section>
  );
}

function ShareButton({ name }: { name: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={async () => {
        const url = window.location.href.split("#")[0];
        try {
          if (navigator.share) await navigator.share({ title: name, url });
          else {
            await navigator.clipboard.writeText(url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }
        } catch {
          // Share sheet dismissed
        }
      }}
    >
      <HugeiconsIcon icon={Link01Icon} /> {copied ? "Link copied" : "Share"}
    </Button>
  );
}

export function ProviderProfile({ slug }: { slug: string }) {
  const { data, isLoading, isError, error, refetch } = useProvider(slug);
  const p = data?.payload.provider;

  if (isLoading) return <div className="mx-auto max-w-6xl px-4 py-10"><LoadingState /></div>;
  if (isError || !p) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        {error?.message?.toLowerCase().includes("not found") || !p ? (
          <>
            <h1 className="text-xl font-semibold">Provider not found</h1>
            <p className="text-muted-foreground mt-2 text-sm">This profile isn&apos;t public, or its listing has lapsed.</p>
            <Link href="/hire" className="mt-6 inline-block"><Button variant="outline">Browse providers</Button></Link>
          </>
        ) : (
          <ErrorState message={error?.message ?? "Could not load this profile"} onRetry={() => refetch()} />
        )}
      </div>
    );
  }

  const level = verifiedLevel(p);
  const meta = [
    { icon: Location01Icon, text: p.service_areas.map(areaLabel).join(", ") || "Area not set" },
    p.languages.length ? { icon: TranslateIcon, text: p.languages.map(languageLabel).join(", ") } : null,
    { icon: Calendar03Icon, text: `Member since ${memberSince(p.approved_at)}` },
    responseLabel(p.response_hours) ? { icon: Clock01Icon, text: responseLabel(p.response_hours)! } : null,
  ].filter(Boolean) as { icon: typeof Location01Icon; text: string }[];

  const stats = [
    { label: "Trust score", value: `${p.trust_score}` },
    p.job_success != null ? { label: "Job Success", value: `${p.job_success}%` } : null,
    { label: "Rating", value: p.rating_count ? p.rating_avg.toFixed(1) : "New" },
    { label: "Jobs done", value: String(p.completed_count) },
    { label: "Experience", value: `${p.experience_years} yr${p.experience_years === 1 ? "" : "s"}` },
  ].filter(Boolean) as { label: string; value: string }[];

  return (
    <div className="pb-12">
      {/* Cover */}
      <div className="bg-primary relative h-52 overflow-hidden md:h-48">
        <svg className="absolute inset-0 h-full w-full opacity-[0.08]" aria-hidden>
          <defs>
            <pattern id="cover-weave" width="28" height="28" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <path d="M0 14h28M14 0v28" stroke="#fff" strokeWidth="6" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#cover-weave)" />
        </svg>
        <div className="relative mx-auto max-w-6xl px-4 pt-4">
          <PageNav label={p.display_name} tone="onDark" />
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4">
        {/* Identity card overlapping the cover */}
        <section className="border-border bg-card relative -mt-20 rounded-xl border p-6 shadow-sm">
          <div className="flex flex-col gap-5 md:flex-row md:items-start">
            <ProviderAvatar name={p.display_name} photoUrl={p.photo_url} entity={p.entity_type} verified={level} size="xl" className="-mt-16 md:-mt-20" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-gov-ink text-2xl font-bold md:text-3xl">{p.display_name}</h1>
                    {p.is_sample && <span className="rounded bg-amber-100 px-1.5 text-[10px] font-semibold text-amber-900">SAMPLE</span>}
                  </div>
                  {p.display_name_am && <p className="text-muted-foreground text-sm">{p.display_name_am}</p>}
                  {p.entity_type === "company" && p.legal_name && p.legal_name !== p.display_name && (
                    <p className="text-muted-foreground text-xs">Registered as {p.legal_name}</p>
                  )}
                </div>
                <ShareButton name={p.display_name} />
              </div>
              {p.headline && <p className="mt-2 text-base md:text-lg">{p.headline}</p>}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <TypeBadge type={p.provider_type} entity={p.entity_type} />
                <VerificationBadges provider={p} />
                {p.registration_no && <span className="text-muted-foreground font-mono text-[11px]">Reg. {p.registration_no}</span>}
              </div>
              <ul className="text-muted-foreground mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs">
                {meta.map((m) => (
                  <li key={m.text} className="flex items-center gap-1.5">
                    <HugeiconsIcon icon={m.icon} className="size-4" />
                    {m.text}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <dl className={cn("border-border mt-6 grid grid-cols-2 gap-4 border-t pt-5", stats.length > 4 ? "sm:grid-cols-5" : "sm:grid-cols-4")}>
            {stats.map((s) => (
              <div key={s.label} className="text-center sm:text-left">
                <dt className="text-muted-foreground text-[11px] uppercase tracking-wide">{s.label}</dt>
                <dd className="text-gov-ink text-xl font-bold tabular-nums">{s.value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0 space-y-6">
            <nav aria-label="Profile sections" className="border-border bg-card sticky top-(--nav-h) z-10 -mx-1 flex gap-1 overflow-x-auto rounded-lg border p-1 text-sm">
              {[
                ["#about", "About"],
                ["#services", "Services"],
                ...(p.provider_type === "agency" ? [["#team", "Team"]] : []),
                ["#reviews", `Reviews (${p.reviews.total})`],
              ].map(([href, label]) => (
                <a key={href} href={href} className="hover:bg-muted shrink-0 rounded-md px-3 py-1.5">
                  {label}
                </a>
              ))}
            </nav>

            <Section id="about" title="About" am="ስለ">
              {p.bio ? <p className="text-sm leading-relaxed whitespace-pre-line">{p.bio}</p> : <p className="text-muted-foreground text-sm">No description yet.</p>}
              {p.highlights.length > 0 && (
                <div className="mt-5">
                  <h3 className="mb-2 text-sm font-semibold">Highlights · ስኬቶች</h3>
                  <ul className="grid gap-2 sm:grid-cols-2">
                    {p.highlights.map((h) => (
                      <li key={h} className="bg-secondary/50 flex gap-2 rounded-lg p-3 text-sm">
                        <span className="text-primary font-bold">✓</span>
                        {h}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {p.agency && (
                <Link href={`/providers/${p.agency.slug}`} className="border-border hover:border-primary mt-5 flex items-center gap-3 rounded-lg border p-3">
                  <ProviderAvatar name={p.agency.display_name} photoUrl={p.agency.photo_url} entity="company" size="sm" />
                  <span className="text-sm">
                    Member of <strong>{p.agency.display_name}</strong>
                    <span className="text-muted-foreground block text-xs">Agency trust score {p.agency.trust_score}</span>
                  </span>
                </Link>
              )}
            </Section>

            <Section id="services" title="Services and specialties" am="የሚሰሩት">
              {p.specialties.length > 0 && (
                <div className="mb-4 flex flex-wrap gap-1.5">
                  {p.specialties.map((k) => (
                    <span key={k} className="bg-secondary text-secondary-foreground rounded-full px-3 py-1 text-xs font-medium">
                      {specialtyLabel(k)}
                    </span>
                  ))}
                </div>
              )}
              {(p.licences ?? []).length > 0 && (
                <ul className="mb-4 space-y-1.5">
                  {(p.licences ?? []).map((l) => (
                    <li key={l.kind} className="text-sm">
                      <span className="font-medium">{l.label}</span>{" "}
                      <span className="text-muted-foreground text-xs">
                        · checked by staff{l.valid_until ? `, valid until ${new Date(l.valid_until).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {(p.delivery_modes ?? []).length > 0 && (
                <p className="mb-4 text-sm">
                  <span className="text-muted-foreground">Works </span>
                  {(p.delivery_modes ?? []).map((m) => DELIVERY_LABELS[m].short.toLowerCase()).join(", ")}
                  {p.visit_fee ? <span className="text-muted-foreground"> · visit fee {p.visit_fee.toLocaleString("en")} ETB</span> : null}
                </p>
              )}
              {p.services.length > 0 ? (
                <ul className="divide-border divide-y">
                  {p.services.map((s) => (
                    <li key={s.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                      <Link href={`/services/${s.id}`} className="hover:text-primary text-sm font-medium hover:underline">{s.name}</Link>
                      <span className="text-muted-foreground text-xs">
                        {s.summary ?? `${s.institution}${s.fee_text ? ` · official fee ${s.fee_text}` : ""}`}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                !p.specialties.length && <p className="text-muted-foreground text-sm">No services listed yet.</p>
              )}
            </Section>

            {p.provider_type === "agency" && (
              <Section id="team" title={`Team (${p.team.length})`} am="ቡድን">
                {p.team.length === 0 ? (
                  <p className="text-muted-foreground text-sm">No team members listed yet.</p>
                ) : (
                  <ul className="grid gap-3 sm:grid-cols-2">
                    {p.team.map((m) => (
                      <li key={m.membership_id}>
                        <Link href={`/providers/${m.slug}`} className="border-border hover:border-primary flex items-center gap-3 rounded-lg border p-3 transition-colors">
                          <ProviderAvatar name={m.display_name} photoUrl={m.photo_url} verified={m.id_verified ? "id" : null} size="sm" />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium">{m.display_name}</span>
                            <span className="text-muted-foreground block text-xs">
                              {m.role_title ?? "Member"} · {m.completed_count} jobs
                            </span>
                          </span>
                          <ScoreBadge score={m.trust_score} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-muted-foreground mt-3 text-xs">The agency&apos;s score includes the work and reviews of its active members.</p>
              </Section>
            )}

            <Reviews provider={p} />
          </div>

          <aside className="min-w-0 space-y-4 lg:sticky lg:top-[calc(var(--nav-h)+1rem)] lg:self-start">
            <section className="border-border bg-card rounded-xl border p-5">
              <p className="text-muted-foreground text-[11px] uppercase tracking-wide">Price</p>
              <p className="text-gov-ink text-xl font-bold">{formatFee(p)}</p>
              {p.pricing_notes && <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{p.pricing_notes}</p>}
              {p.accepting_work ? (
                <a href="#hire" className="bg-primary text-primary-foreground hover:bg-primary/90 mt-4 block rounded-lg px-4 py-2.5 text-center text-sm font-semibold">
                  Hire {p.display_name.split(" ")[0]} · ይቅጠሩ
                </a>
              ) : (
                <p className="bg-muted mt-4 rounded-lg px-3 py-2 text-center text-xs">Not taking new work right now</p>
              )}
              {p.external_license_type && (
                <p className="mt-4 text-xs">
                  <span className="text-muted-foreground">Sector licence: </span>
                  {p.external_license_type}{" "}
                  <span className={p.external_license_status === "verified" ? "text-primary font-medium" : "text-muted-foreground"}>
                    ({p.external_license_status === "verified" ? "checked by staff" : "not yet checked"})
                  </span>
                </p>
              )}
              {p.website && (
                <a href={p.website} target="_blank" rel="noreferrer nofollow" className="text-primary mt-2 block truncate text-xs hover:underline">
                  {p.website.replace(/^https?:\/\//, "")}
                </a>
              )}
            </section>

            <section className="border-border bg-card rounded-xl border p-5">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Trust score</h2>
                <ScoreBadge score={p.trust_score} isNew={p.is_new} />
              </div>
              <ScoreBreakdown parts={p.score_breakdown} />
              <p className="border-border mt-3 border-t pt-3 text-xs">
                {p.job_success != null ? (
                  <>
                    <span className="font-semibold">Job Success {p.job_success}%</span>
                    <span className="text-muted-foreground"> · over {p.closed_jobs ?? 0} closed job{p.closed_jobs === 1 ? "" : "s"} in the last 24 months</span>
                  </>
                ) : (
                  <span className="text-muted-foreground">Job Success: shown after 3 closed jobs</span>
                )}
              </p>
              <Link href="/hire/how-scores-work" className="text-primary mt-3 inline-block text-xs font-medium hover:underline">How scores work</Link>
            </section>

            <div id="hire" className="scroll-mt-28">
              <h2 className="text-gov-ink mb-2 font-semibold">Hire {p.display_name} · ይቅጠሩ</h2>
              {p.accepting_work ? (
                <HireForm
                  providerId={p.slug}
                  providerName={p.display_name}
                  serviceId={p.services.length === 1 ? p.services[0].id : undefined}
                  deliveryModes={p.delivery_modes}
                  visitFee={p.visit_fee}
                  returnTo={`/providers/${p.slug}#hire`}
                />
              ) : (
                <p className="border-border bg-card text-muted-foreground rounded-xl border p-4 text-sm">
                  Not taking new work right now. <Link href={`/hire?type=${p.provider_type}`} className="text-primary underline">See similar providers</Link>.
                </p>
              )}
              <p className="text-muted-foreground mt-2 text-[11px] leading-relaxed">
                Agree the fee before work starts and pay official fees only at the service window. Report a problem from
                My hires if anything goes wrong.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
