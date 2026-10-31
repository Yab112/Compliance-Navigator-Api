"use client";

import { siteUrl } from "@cn/core/config/env";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button, buttonVariants } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Pager } from "@cn/ui/pager";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@cn/ui/card";
import { GRAPH_INSTITUTIONS_PAGE_SIZE, useAdminQuery, useGraphInstitutions, useRunDataSource } from "@cn/core/api/admin";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { AdminPage } from "@/modules/components/admin-page";
import { daysSince, formatDateTime, timeAgo } from "@cn/core/lib/format";
import { STAT_STRIP, StatTile } from "@/modules/shared/stat-tile";
import { ErrorState, EmptyState, LoadingState } from "@/modules/shared/states";
import { cn } from "@cn/core/lib/utils";
import type { CatalogInstitution, CatalogStats, MesobCenter } from "@cn/core/types/catalog";
import { CatalogServices } from "@/modules/catalog/catalog-services";

const STALE_AFTER_DAYS = 7;

const TABS = ["institutions", "services", "centers"] as const;
type Tab = (typeof TABS)[number];
const TAB_TEXT: Record<Tab, { title: string; description: string }> = {
  institutions: {
    title: "Institutions",
    description: "Government institutions that offer services through MESOB, busiest first. Press \u201cServices\u201d to open one institution\u2019s services in the Services tab.",
  },
  services: {
    title: "Services",
    description: "Every service in the snapshot with its fee, time and required documents, as citizens see it on the public site. To correct something, it has to change on mesobcenter.et and then be refreshed here.",
  },
  centers: { title: "MESOB centers", description: "Where citizens can go in person to use these services" },
};

function RefreshButton() {
  const { runSource } = useRunDataSource();
  const [state, setState] = useState<{ busy: boolean; message?: string; error?: boolean }>({ busy: false });
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        loading={state.busy}
        onClick={async () => {
          setState({ busy: true });
          try {
            await runSource("mesob_catalog");
            setState({ busy: false, message: "Refresh started. It runs in the background for a few minutes." });
          } catch (e) {
            setState({ busy: false, error: true, message: getErrorMessage(e, "Couldn't start the refresh") });
          }
        }}
      >
        Refresh from mesobcenter.et
      </Button>
      {state.message && (
        <p className={state.error ? "text-destructive text-[11px]" : "text-muted-foreground text-[11px]"}>
          {state.message}{" "}
          {!state.error && (
            <Link href="/data-sources" className="text-primary underline">
              Follow it in Data sources
            </Link>
          )}
        </p>
      )}
    </div>
  );
}

type InstitutionPick = { id: string; name: string };

function InstitutionsTable({
  logos,
  selected,
  onPick,
}: {
  logos: Record<string, CatalogInstitution>;
  selected: string | null;
  onPick: (inst: InstitutionPick) => void;
}) {
  const uid = useId();
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(GRAPH_INSTITUTIONS_PAGE_SIZE);
  const breakdown = useGraphInstitutions({ q, page, size });
  const rows = breakdown.payload?.items ?? [];

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(input.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [input]);

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${uid}-q`}>Search institutions</Label>
        <Input id={`${uid}-q`} type="search" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Name or short name" />
      </div>
      {breakdown.isLoading ? (
        <LoadingState />
      ) : breakdown.error ? (
        <ErrorState
          error={breakdown.error}
          message={getErrorMessage(breakdown.error, "The knowledge graph could not be loaded")}
          onRetry={() => breakdown.refetch()}
        />
      ) : !rows.length ? (
        <EmptyState
          title={q ? "No institutions match" : "No institutions in the graph"}
          description={q ? "Try another name." : "Refresh the catalog; the refresh also copies it into the knowledge graph."}
        />
      ) : (
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-xs">
            <caption className="sr-only">MESOB institutions and their services</caption>
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">Institution</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Services</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Avg. processing</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Can apply online</th>
                <th scope="col" className="py-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className={cn(breakdown.isFetching && "opacity-60")}>
              {rows.map((r) => {
                const logo = logos[r.id]?.logo_url;
                const name = r.short_name ?? r.name;
                return (
                  <tr key={r.id} className={cn("border-border border-t", selected === r.id && "bg-primary/5")}>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        {logo ? (
                          // eslint-disable-next-line @next/next/no-img-element -- remote MESOB logos
                          <img src={logo} alt="" className="size-6 shrink-0 object-contain" loading="lazy" />
                        ) : (
                          <span className="bg-muted size-6 shrink-0" />
                        )}
                        <div className="min-w-0">
                          <p className="truncate font-medium">{name}</p>
                          <p className="text-muted-foreground truncate text-[11px]">{r.name}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">{r.services}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      {r.avg_minutes != null ? `${Math.round(r.avg_minutes)} min` : "-"}
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">{r.online}</td>
                    <td className="py-2 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!r.services}
                        aria-label={`Show services from ${name}`}
                        onClick={() => onPick({ id: r.id, name })}
                      >
                        Services
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <Pager
        page={page}
        pageSize={size}
        total={breakdown.payload?.total ?? 0}
        onPage={setPage}
        onPageSize={(n) => { setSize(n); setPage(0); }}
      />
    </div>
  );
}

export function CatalogPage() {
  const stats = useAdminQuery<CatalogStats>(["catalog-stats"], apiPaths.catalog.stats);
  const institutions = useAdminQuery<{ institutions: CatalogInstitution[] }>(["catalog-institutions"], apiPaths.catalog.institutions);
  const centers = useAdminQuery<{ centers: MesobCenter[] }>(["catalog-centers"], apiPaths.catalog.centers);
  const [institution, setInstitution] = useState<InstitutionPick | null>(null);

  const s = stats.payload;
  const age = daysSince(s?.fetchedAt);
  const stale = age !== null && age > STALE_AFTER_DAYS;
  const logos = Object.fromEntries((institutions.payload?.institutions ?? []).map((i) => [i.id, i]));

  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tab: Tab = TABS.includes(params.get("tab") as Tab) ? (params.get("tab") as Tab) : "institutions";
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ institutions: null, services: null, centers: null });
  const selectTab = (next: Tab, focus = false) => {
    const sp = new URLSearchParams(window.location.search);
    if (next === "institutions") sp.delete("tab");
    else sp.set("tab", next);
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    if (focus) tabRefs.current[next]?.focus();
  };
  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "institutions", label: "Institutions", count: s?.institutions },
    { id: "services", label: institution ? `Services of ${institution.name}` : "Services", count: institution ? undefined : s?.services },
    { id: "centers", label: "MESOB centers", count: s?.centers },
  ];
  const onKeyDown = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === tab);
    const moves: Record<string, number> = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 };
    if (!(e.key in moves)) return;
    e.preventDefault();
    selectTab(tabs[(moves[e.key] + tabs.length) % tabs.length].id, true);
  };

  return (
    <AdminPage
      title="MESOB catalog"
      description="A copy of the public service list published by MESOB, our data partner, on mesobcenter.et: institutions, services with their required documents, fees and processing times, and the one-stop center locations. The app uses this copy in roadmaps, the knowledge graph and the AI assistant."
      actions={
        <>
          <a href={siteUrl("/services")} target="_blank" rel="noreferrer" className={buttonVariants({ variant: "outline" })}>
            View public catalog
          </a>
          <RefreshButton />
        </>
      }
    >
      {stats.isLoading ? (
        <LoadingState />
      ) : stats.error || !s ? (
        <ErrorState error={stats.error} message={getErrorMessage(stats.error)} onRetry={() => stats.refetch()} />
      ) : (
        <>
          {stale && (
            <div className="mb-4 border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-300">
              ▲ The snapshot is {Math.floor(age ?? 0)} days old. MESOB updates fees and requirements regularly, so
              refresh it so citizens see current information.
            </div>
          )}
          <div className={cn(STAT_STRIP, "grid-cols-2 md:grid-cols-5")}>
            <StatTile label="Snapshot taken" value={timeAgo(s.fetchedAt)} hint={formatDateTime(s.fetchedAt)} tone={stale ? "attention" : "default"} />
            <StatTile label="Institutions" value={s.institutions} />
            <StatTile label="Services (English)" value={s.services} />
            <StatTile label="Services (Amharic)" value={s.servicesAm} />
            <StatTile label="MESOB centers" value={s.centers} />
          </div>
        </>
      )}

      <div
        role="tablist"
        aria-label="Catalog sections"
        className="border-border mt-6 mb-4 flex gap-1 overflow-x-auto overflow-y-hidden border-b [scrollbar-width:none]"
        onKeyDown={onKeyDown}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            ref={(el) => {
              tabRefs.current[t.id] = el;
            }}
            id={`catalog-tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            aria-controls={`catalog-panel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => selectTab(t.id)}
            className={cn(
              "-mb-px shrink-0 border-b-2 border-transparent px-3 py-2 text-xs",
              tab === t.id ? "border-primary font-medium" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
            {t.count != null && <span className="text-muted-foreground tabular-nums"> ({t.count.toLocaleString("en")})</span>}
          </button>
        ))}
      </div>

      <Card role="tabpanel" id={`catalog-panel-${tab}`} aria-labelledby={`catalog-tab-${tab}`}>
        <CardHeader>
          <CardTitle>{TAB_TEXT[tab].title}</CardTitle>
          <CardDescription>{TAB_TEXT[tab].description}</CardDescription>
        </CardHeader>
        {tab === "institutions" && (
          <CardContent>
            <InstitutionsTable
              logos={logos}
              selected={institution?.id ?? null}
              onPick={(inst) => {
                setInstitution(inst);
                selectTab("services");
              }}
            />
          </CardContent>
        )}
        {tab === "services" && (
          <CardContent>
            <CatalogServices institution={institution} onClearInstitution={() => setInstitution(null)} />
          </CardContent>
        )}
        {tab === "centers" && (
          <CardContent>
            {centers.isLoading ? (
              <LoadingState />
            ) : centers.error ? (
              <ErrorState error={centers.error} message={getErrorMessage(centers.error)} onRetry={() => centers.refetch()} />
            ) : !centers.payload?.centers.length ? (
              <EmptyState title="No centers in the snapshot" />
            ) : (
              <ul className="grid gap-x-6 text-xs sm:grid-cols-2 xl:grid-cols-3" aria-label="MESOB centers">
                {centers.payload.centers.map((c) => (
                  <li key={c.id} className="border-border flex items-center justify-between gap-2 border-b py-2">
                    <span className="min-w-0">
                      <span className="block truncate">{c.name}</span>
                      {c.city && <span className="text-muted-foreground block truncate text-[11px]">{c.city}</span>}
                    </span>
                    {c.map_url && (
                      <a
                        href={c.map_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-primary shrink-0 text-[11px] underline"
                        aria-label={`Map of ${c.name}`}
                      >
                        Map
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        )}
      </Card>
    </AdminPage>
  );
}
