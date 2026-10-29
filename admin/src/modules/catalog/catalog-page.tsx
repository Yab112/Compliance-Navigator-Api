"use client";

import { siteUrl } from "@cn/core/config/env";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@cn/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@cn/ui/card";
import { useAdminQuery, useGraphInstitutions, useRunDataSource } from "@cn/core/api/admin";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { AdminPage } from "@/modules/components/admin-page";
import { daysSince, formatDateTime, timeAgo } from "@cn/core/lib/format";
import { StatTile } from "@/modules/shared/stat-tile";
import { ErrorState, EmptyState, LoadingState } from "@/modules/shared/states";
import type { CatalogInstitution, CatalogStats, MesobCenter } from "@cn/core/types/catalog";

const STALE_AFTER_DAYS = 7;

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
            setState({ busy: false, message: "Refresh started, track it under Data sources." });
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
              Open
            </Link>
          )}
        </p>
      )}
    </div>
  );
}

export function CatalogPage() {
  const stats = useAdminQuery<CatalogStats>(["catalog-stats"], apiPaths.catalog.stats);
  const institutions = useAdminQuery<{ institutions: CatalogInstitution[] }>(["catalog-institutions"], apiPaths.catalog.institutions);
  const centers = useAdminQuery<{ centers: MesobCenter[] }>(["catalog-centers"], apiPaths.catalog.centers);
  const breakdown = useGraphInstitutions();

  const s = stats.payload;
  const age = daysSince(s?.fetchedAt);
  const stale = age !== null && age > STALE_AFTER_DAYS;
  const logos = Object.fromEntries((institutions.payload?.institutions ?? []).map((i) => [i.id, i]));
  const rows = breakdown.payload?.institutions ?? [];

  return (
    <AdminPage
      title="MESOB catalog"
      description="The public service catalog behind mesobcenter.et: institutions, services with required documents, fees and processing times, and one-stop center locations. It feeds the knowledge graph, roadmaps and the AI assistant."
      actions={
        <>
          <a href={siteUrl("/services")} target="_blank" rel="noreferrer">
            <Button variant="outline">View public catalog</Button>
          </a>
          <RefreshButton />
        </>
      }
    >
      {stats.isLoading ? (
        <LoadingState />
      ) : stats.error || !s ? (
        <ErrorState message={getErrorMessage(stats.error)} onRetry={() => stats.refetch()} />
      ) : (
        <>
          {stale && (
            <div className="mb-4 border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-300">
              ▲ The snapshot is {Math.floor(age ?? 0)} days old. MESOB updates fees and requirements regularly, so
              refresh it so citizens see current information.
            </div>
          )}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatTile label="Snapshot taken" value={timeAgo(s.fetchedAt)} hint={formatDateTime(s.fetchedAt)} tone={stale ? "attention" : "default"} />
            <StatTile label="Institutions" value={s.institutions} />
            <StatTile label="Services (English)" value={s.services} />
            <StatTile label="Services (Amharic)" value={s.servicesAm} />
            <StatTile label="MESOB centers" value={s.centers} />
          </div>
        </>
      )}

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Institutions</CardTitle>
            <CardDescription>English services per institution as mirrored in the knowledge graph</CardDescription>
          </CardHeader>
          <CardContent>
            {breakdown.isLoading ? (
              <LoadingState />
            ) : breakdown.error ? (
              <ErrorState message={getErrorMessage(breakdown.error)} onRetry={() => breakdown.refetch()} />
            ) : !rows.length ? (
              <EmptyState title="No institutions in the graph" description="Run “MESOB → knowledge graph” under Data sources." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-left text-xs">
                  <thead className="text-muted-foreground text-[11px]">
                    <tr>
                      <th className="py-2 pr-3 font-medium">Institution</th>
                      <th className="py-2 pr-3 text-right font-medium">Services</th>
                      <th className="py-2 pr-3 text-right font-medium">Avg. processing</th>
                      <th className="py-2 text-right font-medium">Online link</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const logo = logos[r.id]?.logo_url;
                      return (
                        <tr key={r.id} className="border-border border-t">
                          <td className="py-2 pr-3">
                            <div className="flex items-center gap-2">
                              {logo ? (
                                // eslint-disable-next-line @next/next/no-img-element -- remote MESOB logos
                                <img src={logo} alt="" className="size-6 shrink-0 object-contain" loading="lazy" />
                              ) : (
                                <span className="bg-muted size-6 shrink-0" />
                              )}
                              <div className="min-w-0">
                                <p className="truncate font-medium">{r.short_name ?? r.name}</p>
                                <p className="text-muted-foreground truncate text-[11px]">{r.name}</p>
                              </div>
                            </div>
                          </td>
                          <td className="py-2 pr-3 text-right tabular-nums">{r.services}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">
                            {r.avg_minutes != null ? `${Math.round(r.avg_minutes)} min` : "-"}
                          </td>
                          <td className="py-2 text-right tabular-nums">{r.online}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>MESOB centers</CardTitle>
            <CardDescription>One-stop service center locations</CardDescription>
          </CardHeader>
          <CardContent>
            {centers.isLoading ? (
              <LoadingState />
            ) : centers.error ? (
              <ErrorState message={getErrorMessage(centers.error)} onRetry={() => centers.refetch()} />
            ) : !centers.payload?.centers.length ? (
              <EmptyState title="No centers in the snapshot" />
            ) : (
              <ul className="divide-border divide-y">
                {centers.payload.centers.map((c) => (
                  <li key={c.id} className="flex items-center justify-between gap-2 py-2">
                    <span className="min-w-0 truncate">{c.name}</span>
                    {c.map_url && (
                      <a href={c.map_url} target="_blank" rel="noreferrer" className="text-primary shrink-0 text-[11px] underline">
                        Map
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </AdminPage>
  );
}
