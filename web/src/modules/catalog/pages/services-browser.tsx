"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useServiceDirectory } from "@/api/catalog";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { EmptyState, ErrorState, LoadingState, useDebounced } from "@/modules/guday/components/shared";
import type { DirectoryItem, DirectorySource } from "@/types/catalog";

const PAGE_SIZE = 20;

const SOURCE_META: Record<DirectorySource, { label: string; am: string; badge: string; className: string; hint: string }> = {
  organization: {
    label: "Published by organizations",
    am: "በተቋማት የቀረበ",
    badge: "Published by the organization",
    className: "bg-primary text-primary-foreground",
    hint: "Requirements, fees and branches entered and kept current by the organization itself.",
  },
  path: {
    label: "Guided paths",
    am: "የተመሩ ሂደቶች",
    badge: "Guided path",
    className: "bg-gov-yellow text-gov-ink",
    hint: "We build the full chain across every office involved, starting from what you already have.",
  },
  mesob: {
    label: "MESOB catalog (partner)",
    am: "የመሶብ ካታሎግ",
    badge: "MESOB catalog",
    className: "bg-secondary text-secondary-foreground",
    hint: "Services available at MESOB one-stop centers, from our partner's public catalog.",
  },
};

function fee(item: DirectoryItem): string | null {
  if (item.feeMin === 0) return "Free";
  if (item.feeMin != null) {
    const min = Number(item.feeMin).toLocaleString("en");
    return item.feeMax != null && item.feeMax !== item.feeMin
      ? `${min} to ${Number(item.feeMax).toLocaleString("en")} ${item.feeCurrency}`
      : `${min} ${item.feeCurrency}`;
  }
  return item.feeText ? "See fee details" : null;
}

function ServiceRow({ item }: { item: DirectoryItem }) {
  const meta = SOURCE_META[item.source];
  const price = fee(item);
  return (
    <li>
      <Link href={item.href} className="hover:bg-secondary/40 flex gap-4 p-4">
        <span className="border-border bg-card flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-md border">
          {item.providerLogo ? (
            // eslint-disable-next-line @next/next/no-img-element -- logos come from organizations and the partner catalog
            <img src={item.providerLogo} alt="" className="size-9 object-contain" />
          ) : (
            <span className="text-primary text-xs font-bold">{(item.provider ?? item.title).slice(0, 2).toUpperCase()}</span>
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{item.title}</p>
            {item.titleAm && <span className="text-muted-foreground text-sm">· {item.titleAm}</span>}
          </div>
          <p className="text-muted-foreground mt-0.5 text-sm">
            {item.provider}
            {item.verified && <span className="text-primary ml-1.5 text-xs font-semibold">✓ Verified organization</span>}
          </p>
          {item.summary && <p className="text-muted-foreground mt-1 line-clamp-1 text-sm">{item.summary}</p>}
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            <span className={cn("rounded px-2 py-0.5 font-medium", meta.className)}>{meta.badge}</span>
            {price && <span className="border-border rounded border px-2 py-0.5">{price}</span>}
            {item.time && <span className="border-border max-w-56 truncate rounded border px-2 py-0.5">{item.time}</span>}
            {item.documentCount > 0 && (
              <span className="border-border rounded border px-2 py-0.5">
                {item.documentCount} {item.source === "path" ? "prerequisites" : "documents"}
              </span>
            )}
          </div>
        </div>
      </Link>
    </li>
  );
}

export function ServicesBrowser() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const source = (params.get("source") as DirectorySource | null) ?? undefined;
  const language = params.get("lang") === "am" ? "am" : "en";
  const page = Math.max(0, Number(params.get("page") ?? 0) || 0);
  const q = useDebounced(query.trim(), 300);

  const setParam = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  // Keep the URL in sync with the debounced search box
  useEffect(() => {
    if ((params.get("q") ?? "") !== q) setParam({ q: q || null, page: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const { data, isLoading, isError, error, refetch, isFetching } = useServiceDirectory({
    q: q || undefined,
    source,
    language,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const result = data?.payload;
  const counts = result?.counts;
  const allCount = counts ? counts.organization + counts.path + counts.mesob : undefined;
  const pages = Math.ceil((result?.total ?? 0) / PAGE_SIZE);

  return (
    <PageShell
      title="Services · አገልግሎቶች"
      description="Every service on the platform in one place: services organizations publish themselves, guided paths that connect several offices, and the catalog of our partner MESOB."
    >
      <div className="mb-4 grid gap-2 sm:grid-cols-[1fr_auto]">
        <label htmlFor="service-search" className="sr-only">
          Search services
        </label>
        <Input
          id="service-search"
          className="h-10"
          placeholder="Search a service, an organization or a document (e.g. trade license, TIN, lease)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="flex" role="group" aria-label="Language">
          {(["en", "am"] as const).map((lang) => (
            <Button
              key={lang}
              type="button"
              className="h-10"
              variant={language === lang ? "default" : "outline"}
              aria-pressed={language === lang}
              onClick={() => setParam({ lang: lang === "en" ? null : lang, page: null })}
            >
              {lang === "en" ? "English" : "አማርኛ"}
            </Button>
          ))}
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-2" role="group" aria-label="Source">
        <button
          type="button"
          onClick={() => setParam({ source: null, page: null })}
          className={cn(
            "rounded-full border px-3 py-1.5 text-sm",
            !source ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary",
          )}
        >
          All services{allCount != null && ` · ${allCount}`}
        </button>
        {(Object.keys(SOURCE_META) as DirectorySource[]).map((key) => (
          <button
            key={key}
            type="button"
            title={SOURCE_META[key].hint}
            onClick={() => setParam({ source: source === key ? null : key, page: null })}
            className={cn(
              "rounded-full border px-3 py-1.5 text-sm",
              source === key ? "border-primary bg-primary text-primary-foreground" : "border-border hover:border-primary",
            )}
          >
            {SOURCE_META[key].label}
            {counts && ` · ${counts[key]}`}
          </button>
        ))}
      </div>

      {source && <p className="text-muted-foreground -mt-3 mb-4 text-sm">{SOURCE_META[source].hint}</p>}

      {isLoading ? (
        <LoadingState label="Loading services…" />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load services"} onRetry={() => refetch()} />
      ) : !result?.items.length ? (
        <EmptyState title="No services match">
          <p>Try a shorter search or another source.</p>
          <p className="mt-3">
            Is your organization missing?{" "}
            <Link href="/organizations/join" className="text-primary font-medium underline">
              Publish your services for free
            </Link>
          </p>
        </EmptyState>
      ) : (
        <>
          <p className="text-muted-foreground mb-2 text-xs" aria-live="polite">
            {result.total} result{result.total === 1 ? "" : "s"}
            {isFetching && " · updating…"}
          </p>
          <ul className="divide-border border-border bg-card divide-y rounded-md border">
            {result.items.map((item) => (
              <ServiceRow key={item.id} item={item} />
            ))}
          </ul>
          {pages > 1 && (
            <nav className="mt-4 flex items-center justify-between text-xs" aria-label="Pagination">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setParam({ page: page - 1 ? String(page - 1) : null })}>
                Previous
              </Button>
              <span className="text-muted-foreground">
                Page {page + 1} of {pages}
              </span>
              <Button variant="outline" size="sm" disabled={page + 1 >= pages} onClick={() => setParam({ page: String(page + 1) })}>
                Next
              </Button>
            </nav>
          )}
        </>
      )}

      <aside className="bg-gov-ink mt-10 flex flex-wrap items-center justify-between gap-4 rounded-md p-6 text-white">
        <div>
          <p className="font-semibold">Do you give a service people need? · አገልግሎት ይሰጣሉ?</p>
          <p className="mt-1 text-sm text-white/75">
            Publish your services, documents, fees and branches for free. People arrive at your window prepared.
          </p>
        </div>
        <Link href="/organizations/join" className="bg-gov-yellow text-gov-ink rounded-md px-5 py-2.5 text-sm font-semibold hover:brightness-95">
          Register your organization
        </Link>
      </aside>
    </PageShell>
  );
}
