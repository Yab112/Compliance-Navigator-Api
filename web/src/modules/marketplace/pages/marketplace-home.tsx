"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { FilterHorizontalIcon, Search01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useProviders } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { cn } from "@cn/core/lib/utils";
import { ErrorState, LANGUAGE_OPTIONS, NativeSelect, useDebounced } from "@cn/ui/guday/shared";
import type { ProviderType, SortKey } from "@cn/core/types/provider";
import { ProviderCard, ProviderCardSkeleton } from "@/modules/marketplace/components/provider-card";
import { AREA_OPTIONS, SPECIALTIES, TYPE_META, TYPE_ORDER, specialtyLabel } from "@cn/ui/marketplace/constants";
import { PageNav } from "@cn/ui/layout/page-nav";

const PAGE_SIZE = 24;
const PRICE_STEPS = [0, 500, 1000, 2500, 5000, 10000];

/** "1 Guday Geday agent", "28 Guday Geday agents", "1 agency": keeps the Guday Geday name capitalized. */
function resultNoun(type: ProviderType, n: number): string {
  if (type === "guday_geday") return n === 1 ? "Guday Geday agent" : "Guday Geday agents";
  return n === 1 ? TYPE_META[type].label.toLowerCase() : TYPE_META[type].plural.toLowerCase();
}

type Filters = {
  type: ProviderType;
  specialty: string;
  area: string;
  verifiedOnly: boolean;
  minScore: number;
  entity: string;
  language: string;
  maxFee: number;
};

function FilterPanel({ f, setParam, onDone }: { f: Filters; setParam: (u: Record<string, string | null>) => void; onDone?: () => void }) {
  const active = [f.specialty, f.area, f.entity, f.language].filter(Boolean).length + (f.verifiedOnly ? 1 : 0) + (f.minScore ? 1 : 0) + (f.maxFee ? 1 : 0);
  return (
    <div className="space-y-5 text-sm">
      {SPECIALTIES[f.type].length > 0 && (
        <fieldset>
          <legend className="mb-2 text-xs font-semibold">Specialty · ዘርፍ</legend>
          <div className="flex flex-wrap gap-1.5">
            {["", ...SPECIALTIES[f.type]].map((s) => (
              <button
                key={s || "all"}
                type="button"
                aria-pressed={f.specialty === s}
                onClick={() => setParam({ specialty: s || null })}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs",
                  f.specialty === s ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:border-primary/50",
                )}
              >
                {s ? specialtyLabel(s, true) : "All"}
              </button>
            ))}
          </div>
        </fieldset>
      )}
      <div>
        <label htmlFor="mk-entity" className="mb-1 block text-xs font-semibold">
          Provider · አቅራቢ
        </label>
        <NativeSelect id="mk-entity" value={f.entity} onChange={(e) => setParam({ entity: e.target.value || null })} className="h-9 rounded-md text-sm">
          <option value="">Individuals and companies</option>
          <option value="individual">Individuals</option>
          <option value="company">Companies</option>
        </NativeSelect>
      </div>
      <div>
        <label htmlFor="mk-score" className="mb-1 flex justify-between text-xs font-semibold">
          <span>Minimum trust score</span>
          <span className="text-primary tabular-nums">{f.minScore ? `${f.minScore}+` : "Any"}</span>
        </label>
        <input
          id="mk-score"
          type="range"
          min={0}
          max={90}
          step={5}
          value={f.minScore}
          onChange={(e) => setParam({ min_score: e.target.value === "0" ? null : e.target.value })}
          className="accent-primary w-full"
        />
      </div>
      <div>
        <label htmlFor="mk-fee" className="mb-1 block text-xs font-semibold">
          Starting price up to
        </label>
        <NativeSelect id="mk-fee" value={String(f.maxFee)} onChange={(e) => setParam({ max_fee: e.target.value === "0" ? null : e.target.value })} className="h-9 rounded-md text-sm">
          {PRICE_STEPS.map((p) => (
            <option key={p} value={p}>
              {p ? `${p.toLocaleString("en")} ETB` : "Any price"}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div>
        <label htmlFor="mk-lang" className="mb-1 block text-xs font-semibold">
          Speaks · ቋንቋ
        </label>
        <NativeSelect id="mk-lang" value={f.language} onChange={(e) => setParam({ language: e.target.value || null })} className="h-9 rounded-md text-sm">
          <option value="">Any language</option>
          {LANGUAGE_OPTIONS.filter((l) => l.value !== "other").map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </NativeSelect>
      </div>
      <label className="flex cursor-pointer items-start gap-2 text-xs">
        <input
          type="checkbox"
          className="accent-primary mt-0.5 size-4"
          checked={f.verifiedOnly}
          onChange={(e) => setParam({ verified: e.target.checked ? "1" : null })}
        />
        <span>
          <span className="font-semibold">Fayda ID verified only</span>
          <span className="text-muted-foreground block">Identity checked against the national ID</span>
        </span>
      </label>
      <div className="flex gap-2">
        {active > 0 && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setParam({ specialty: null, entity: null, min_score: null, max_fee: null, language: null, verified: null })}
          >
            Clear filters ({active})
          </Button>
        )}
        {onDone && (
          <Button type="button" size="sm" onClick={onDone}>
            Show results
          </Button>
        )}
      </div>
    </div>
  );
}

export function MarketplaceHome() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const f: Filters = {
    type: (TYPE_ORDER.includes(params.get("type") as ProviderType) ? params.get("type") : "guday_geday") as ProviderType,
    specialty: params.get("specialty") ?? "",
    area: params.get("area") ?? params.get("sub_city") ?? "",
    verifiedOnly: params.get("verified") === "1",
    minScore: Number(params.get("min_score") ?? 0) || 0,
    entity: params.get("entity") ?? "",
    language: params.get("language") ?? "",
    maxFee: Number(params.get("max_fee") ?? 0) || 0,
  };
  const sort = (params.get("sort") as SortKey) || "score";
  const serviceId = params.get("service_id") ?? "";
  const page = Math.max(0, Number(params.get("page") ?? 0) || 0);
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [sheet, setSheet] = useState(false);
  const q = useDebounced(query.trim(), 300);

  const setParam = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!("page" in updates)) next.delete("page");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== q) setParam({ q: q || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const { data, isLoading, isError, error, refetch, isFetching } = useProviders({
    type: f.type,
    specialty: f.specialty || undefined,
    area: f.area || undefined,
    verified_only: f.verifiedOnly || undefined,
    min_score: f.minScore || undefined,
    entity: (f.entity || undefined) as "individual" | "company" | undefined,
    language: f.language || undefined,
    max_fee: f.maxFee || undefined,
    service_id: serviceId || undefined,
    q: q || undefined,
    sort,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const payload = data?.payload;
  const counts = payload?.countsByType ?? {};
  const pages = Math.ceil((payload?.total ?? 0) / PAGE_SIZE);

  return (
    <div>
      {/* Hero search */}
      <section className="bg-gov-ink text-white">
        <div className="mx-auto max-w-6xl px-4 py-10 md:py-12">
          <PageNav label="Hire" tone="onDark" />
          <p className="text-gov-yellow text-sm font-semibold">ታማኝ አገልግሎት ሰጪ ይቅጠሩ</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight md:text-4xl">Hire a verified provider</h1>
          <p className="mt-2 max-w-2xl text-sm text-white/75 md:text-base">
            Guday Geday agents and agencies with checked identities, a public trust score and reviews written
            only by people who actually hired them.
          </p>
          <form
            role="search"
            onSubmit={(e) => e.preventDefault()}
            className="mt-6 grid max-w-3xl gap-2 rounded-xl bg-white p-2 shadow-lg sm:grid-cols-[1fr_200px_auto]"
          >
            <label className="flex items-center gap-2 px-2">
              <HugeiconsIcon icon={Search01Icon} className="text-muted-foreground size-5 shrink-0" />
              <span className="sr-only">What do you need?</span>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="What do you need? Name, service or registration no."
                className="text-foreground h-10 min-w-0 flex-1 bg-transparent text-sm outline-none"
              />
            </label>
            <label className="border-border flex items-center sm:border-l sm:pl-2">
              <span className="sr-only">Area</span>
              <select
                value={f.area}
                onChange={(e) => setParam({ area: e.target.value || null, sub_city: null })}
                className="text-foreground h-10 w-full bg-transparent px-2 text-sm outline-none"
              >
                <option value="">Anywhere</option>
                {AREA_OPTIONS.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className="bg-gov-yellow text-gov-ink rounded-lg px-5 py-2 text-sm font-semibold hover:brightness-95">
              Search
            </button>
          </form>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-white/70">
            <span>✓ Fayda ID checked</span>
            <span>✓ Licences reviewed by staff</span>
            <span>✓ Reviews only from real clients</span>
            <Link href="/hire/how-scores-work" className="text-gov-yellow font-medium hover:underline">
              How trust scores work
            </Link>
          </div>
        </div>
      </section>

      {/* Type tabs */}
      <div className="border-border bg-card sticky top-(--nav-h) z-20 border-b">
        <div role="tablist" aria-label="Provider type" className="mx-auto flex max-w-6xl gap-1 overflow-x-auto overflow-y-hidden px-4 [scrollbar-width:none]">
          {TYPE_ORDER.map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={f.type === t}
              onClick={() => setParam({ type: t, specialty: null })}
              className={cn(
                "-mb-px flex shrink-0 items-center gap-2 border-b-[3px] px-4 py-3 text-sm",
                f.type === t ? "border-primary text-primary font-semibold" : "text-muted-foreground hover:text-foreground border-transparent",
              )}
            >
              {TYPE_META[t].label}
              <span className="hidden text-xs opacity-70 sm:inline">· {TYPE_META[t].am}</span>
              <span className={cn("rounded-full px-2 text-[11px] tabular-nums", f.type === t ? "bg-primary/10" : "bg-muted")}>{counts[t] ?? 0}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-muted-foreground mb-4 max-w-3xl text-xs leading-relaxed">
          {TYPE_META[f.type].blurb}{" "}
          <Link href={`/providers/join?type=${f.type}`} className="text-primary font-semibold hover:underline">
            Are you a {TYPE_META[f.type].label.toLowerCase()}? List yourself →
          </Link>
        </p>
        <div>
          <section aria-live="polite" className="min-w-0">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm">
                {payload ? (
                  <>
                    <strong>{payload.total}</strong> {resultNoun(f.type, payload.total)}
                    {f.area ? ` in ${AREA_OPTIONS.find((a) => a.value === f.area)?.label ?? f.area}` : ""}
                  </>
                ) : (
                  " "
                )}
                {isFetching && !isLoading ? <span className="text-muted-foreground"> · updating</span> : null}
              </p>
              <div className="flex items-center gap-2">
                <Button type="button" variant="ghost" size="sm" onClick={() => setSheet(true)}>
                  <HugeiconsIcon icon={FilterHorizontalIcon} /> Filters
                </Button>
                <label className="flex items-center gap-2 text-xs">
                  <span className="hidden sm:inline">Sort by</span>
                  <NativeSelect value={sort} onChange={(e) => setParam({ sort: e.target.value })} className="h-8 w-36 rounded-md" aria-label="Sort by">
                    <option value="score">Trust score</option>
                    <option value="rating">Rating</option>
                    <option value="reviews">Most reviewed</option>
                    <option value="newest">Newest</option>
                  </NativeSelect>
                </label>
              </div>
            </div>

            {serviceId && (
              <button type="button" onClick={() => setParam({ service_id: null })} className="border-primary text-primary mb-4 rounded-full border px-3 py-1 text-xs">
                Showing providers for one service ✕
              </button>
            )}

            {isLoading ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <ProviderCardSkeleton key={i} />
                ))}
              </div>
            ) : isError ? (
              <ErrorState message={error?.message ?? "Could not load providers"} onRetry={() => refetch()} />
            ) : !payload?.items.length && page > 0 && pages > 0 ? (
              <div className="border-border bg-card rounded-xl border px-6 py-14 text-center">
                <p className="text-lg font-semibold">This page is past the end</p>
                <p className="text-muted-foreground mx-auto mt-2 max-w-md text-sm">
                  There {pages === 1 ? "is only 1 page" : `are only ${pages} pages`} of results.
                </p>
                <div className="mt-5 flex justify-center">
                  <Button variant="outline" onClick={() => setParam({ page: pages > 1 ? String(pages - 1) : null })}>
                    Go to the last page
                  </Button>
                </div>
              </div>
            ) : !payload?.items.length ? (
              <div className="border-border bg-card rounded-xl border px-6 py-14 text-center">
                <p className="text-lg font-semibold">No providers match these filters</p>
                <p className="text-muted-foreground mx-auto mt-2 max-w-md text-sm">
                  Try another area, lower the minimum score, or clear the filters. Staff can also assign a provider if you
                  send a request from a service page.
                </p>
                <div className="mt-5 flex justify-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setParam({ specialty: null, entity: null, min_score: null, max_fee: null, language: null, verified: null, area: null })}
                  >
                    Clear filters
                  </Button>
                  <Link href={`/providers/join?type=${f.type}`}>
                    <Button>List yourself</Button>
                  </Link>
                </div>
              </div>
            ) : (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  {payload.items.map((p) => (
                    <ProviderCard key={p.id} provider={p} />
                  ))}
                </div>
                {pages > 1 && (
                  <nav aria-label="Pages" className="mt-8 flex items-center justify-center gap-1 text-sm">
                    <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setParam({ page: page > 1 ? String(page - 1) : null })}>
                      Previous
                    </Button>
                    {Array.from({ length: pages }, (_, i) => i)
                      .filter((i) => Math.abs(i - page) <= 2 || i === 0 || i === pages - 1)
                      .map((i) => (
                        <Button
                          key={i}
                          size="sm"
                          variant={i === page ? "default" : "ghost"}
                          aria-current={i === page ? "page" : undefined}
                          onClick={() => setParam({ page: i ? String(i) : null })}
                        >
                          {i + 1}
                        </Button>
                      ))}
                    <Button size="sm" variant="outline" disabled={page + 1 >= pages} onClick={() => setParam({ page: String(page + 1) })}>
                      Next
                    </Button>
                  </nav>
                )}
              </>
            )}
          </section>
        </div>
      </div>

      {/* Filters: a sheet from the bottom on phones, a panel from the right on wider screens */}
      {sheet && (
        <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-label="Filters">
          <button type="button" aria-label="Close filters" className="absolute inset-0 bg-black/40" onClick={() => setSheet(false)} />
          <div className="bg-card absolute inset-x-0 bottom-0 max-h-[85dvh] overflow-y-auto rounded-t-2xl p-5 shadow-xl md:inset-y-0 md:right-0 md:left-auto md:max-h-none md:w-96 md:rounded-none">
            <div className="mb-4 flex items-center justify-between">
              <p className="font-semibold">Filters · ማጣሪያ</p>
              <button type="button" className="text-muted-foreground text-sm" onClick={() => setSheet(false)}>
                Close
              </button>
            </div>
            <FilterPanel f={f} setParam={setParam} onDone={() => setSheet(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
