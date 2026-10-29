import Link from "next/link";
import { Location01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import type { PublicProvider } from "@cn/core/types/provider";
import { areaLabel, formatFee, specialtyLabel } from "@cn/ui/marketplace/constants";
import { ProviderAvatar, verifiedLevel } from "@cn/ui/marketplace/provider-avatar";
import { ScoreBadge, Stars, TypeBadge } from "@cn/ui/marketplace/trust";

/** Directory card: who they are, how trusted, what they cost. */
export function ProviderCard({ provider: p }: { provider: PublicProvider }) {
  const areas = p.service_areas.slice(0, 2).map(areaLabel).join(", ") + (p.service_areas.length > 2 ? ` +${p.service_areas.length - 2}` : "");
  const level = verifiedLevel(p);
  return (
    <article className="group border-border bg-card hover:border-primary/60 relative flex flex-col rounded-xl border p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition hover:shadow-md">
      <div className="flex items-start gap-4">
        <ProviderAvatar name={p.display_name} photoUrl={p.photo_url} entity={p.entity_type} verified={level} size="md" />
        <div className="min-w-0 flex-1">
          <Link
            href={`/providers/${p.slug}`}
            className="text-gov-ink line-clamp-1 text-base font-semibold after:absolute after:inset-0 hover:underline"
          >
            {p.display_name}
          </Link>
          {p.headline && <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs leading-relaxed">{p.headline}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <TypeBadge type={p.provider_type} entity={p.entity_type} />
            {level && (
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap text-emerald-800">
                {level === "company" ? "Registered company" : "ID verified"}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs">
        <span className="relative z-10">
          <ScoreBadge score={p.trust_score} parts={p.score_breakdown} isNew={p.rating_count < 3} />
        </span>
        {p.job_success != null && (
          <span title={`Over ${p.closed_jobs ?? 0} closed jobs in the last 24 months`}>
            <span className="text-muted-foreground">Job Success</span> <strong>{p.job_success}%</strong>
          </span>
        )}
        {p.rating_count ? (
          <span className="flex items-center gap-1">
            <Stars value={p.rating_avg} />
            <span className="font-semibold">{p.rating_avg.toFixed(1)}</span>
            <span className="text-muted-foreground">({p.rating_count})</span>
          </span>
        ) : (
          <span className="text-muted-foreground">No reviews yet</span>
        )}
        <span>
          <strong>{p.completed_count}</strong> <span className="text-muted-foreground">job{p.completed_count === 1 ? "" : "s"} done</span>
        </span>
      </div>

      {p.specialties.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {p.specialties.slice(0, 2).map((k) => (
            <span key={k} className="bg-secondary text-secondary-foreground rounded-full px-2 py-0.5 text-[11px]">
              {specialtyLabel(k, true)}
            </span>
          ))}
          {p.specialties.length > 2 && <span className="text-muted-foreground px-1 text-[11px]">+{p.specialties.length - 2}</span>}
        </div>
      )}

      <p className="text-muted-foreground mt-3 flex items-center gap-1 text-xs">
        <HugeiconsIcon icon={Location01Icon} className="size-3.5 shrink-0" />
        {areas || "Area not set"}
      </p>

      <div className="border-border mt-auto flex items-center justify-between gap-2 border-t pt-4">
        <span className="min-w-0">
          <span className="text-muted-foreground block text-[10px] uppercase tracking-wide">Starting at</span>
          <span className="block truncate text-sm font-semibold">{formatFee(p)}</span>
        </span>
        <span className="relative z-10 flex shrink-0 gap-1.5">
          <Link href={`/providers/${p.slug}`} className="border-border hover:bg-muted rounded-md border px-3 py-1.5 text-xs font-medium">
            Profile
          </Link>
          {p.accepting_work && (
            <Link href={`/providers/${p.slug}#hire`} className="bg-primary text-primary-foreground hover:bg-primary/90 rounded-md px-3 py-1.5 text-xs font-semibold">
              Hire
            </Link>
          )}
        </span>
      </div>
    </article>
  );
}

export function ProviderCardSkeleton() {
  return (
    <div className="border-border bg-card animate-pulse rounded-xl border p-5" aria-hidden>
      <div className="flex gap-4">
        <div className="bg-muted size-14 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="bg-muted h-4 w-2/3 rounded" />
          <div className="bg-muted h-3 w-full rounded" />
          <div className="bg-muted h-3 w-1/3 rounded" />
        </div>
      </div>
      <div className="bg-muted mt-5 h-3 w-1/2 rounded" />
      <div className="bg-muted mt-3 h-3 w-1/3 rounded" />
      <div className="bg-muted mt-6 h-8 w-full rounded" />
    </div>
  );
}
