"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useAdminProviders, useMarketAction, useMarketStats } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import {
  AgentStatusBadge,
  EmptyState,
  ErrorState,
  IdVerifiedBadge,
  LoadingState,
  formatDate,
  useDebounced,
} from "@cn/ui/guday/shared";
import { ScoreBadge } from "@cn/ui/marketplace/trust";
import { TYPE_META, TYPE_ORDER } from "@cn/ui/marketplace/constants";
import type { ProviderStatus, ProviderType } from "@cn/core/types/provider";
import { ProviderAvatar, verifiedLevel } from "@cn/ui/marketplace/provider-avatar";

const STATUS_TABS: { value: ProviderStatus | "all"; label: string }[] = [
  { value: "pending", label: "Pending review" },
  { value: "approved", label: "Approved" },
  { value: "suspended", label: "Suspended" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];
const PAGE_SIZE = 50;

export function AdminProviders() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const rawStatus = params.get("status");
  const status = (STATUS_TABS.some((t) => t.value === rawStatus) ? rawStatus : "pending") as ProviderStatus | "all";
  const type = (TYPE_ORDER.includes(params.get("type") as ProviderType) ? params.get("type") : "") as ProviderType | "";
  const licensePending = params.get("license") === "pending";
  const page = Math.max(0, Number(params.get("page") ?? 0) || 0);
  const [query, setQuery] = useState(params.get("q") ?? "");
  const q = useDebounced(query.trim(), 300);
  const purge = useMarketAction();
  const [confirmPurge, setConfirmPurge] = useState(false);

  const setParam = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== q) setParam({ q: q || null, page: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const stats = useMarketStats().data?.payload;
  const { data, isLoading, isError, error, refetch } = useAdminProviders({
    status: status === "all" || licensePending ? undefined : status,
    type: type || undefined,
    license_status: licensePending ? "pending" : undefined,
    q: q || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const items = data?.payload.items ?? [];
  const total = data?.payload.total ?? 0;
  const counts = stats?.agents ?? {};

  return (
    <AdminPage
      title="Marketplace providers · አገልግሎት ሰጪዎች"
      description="Guday Geday agents and agencies. Approve applications, check sector licences and watch trust scores."
      actions={
        confirmPurge ? (
          <>
            <Button
              size="sm"
              variant="destructive"
              loading={purge.isPending}
              onClick={async () => {
                await purge.run(apiPaths.admin.marketPurgeSamples, MTD.POST);
                setConfirmPurge(false);
              }}
            >
              Delete all sample providers, hires and reviews
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirmPurge(false)}>Keep them</Button>
          </>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setConfirmPurge(true)}>
            Remove sample data
          </Button>
        )
      }
    >
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          { label: "Awaiting review", value: counts.pending ?? 0, accent: (counts.pending ?? 0) > 0 },
          { label: "Approved providers", value: counts.approved ?? 0 },
          { label: "Licences to check", value: stats?.licensesPending ?? 0, accent: (stats?.licensesPending ?? 0) > 0, href: "?license=pending&status=all" },
          { label: "Open complaints", value: stats?.openDisputes ?? 0, accent: (stats?.openDisputes ?? 0) > 0, href: "/marketplace/hires?disputed=1" },
          { label: "Reviews (hidden)", value: `${stats?.reviews ?? 0} (${stats?.hiddenReviews ?? 0})`, href: "/marketplace/reviews" },
        ].map((tile) => {
          const body = (
            <div className={cn("border-border h-full border p-3", tile.accent && "border-amber-500/60")}>
              <p className="text-muted-foreground text-[11px]">{tile.label}</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">{stats ? tile.value : "…"}</p>
            </div>
          );
          return tile.href ? <Link key={tile.label} href={tile.href} className="hover:bg-muted/50">{body}</Link> : <div key={tile.label}>{body}</div>;
        })}
      </div>

      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        {[{ v: "", l: "All types" }, ...TYPE_ORDER.map((t) => ({ v: t, l: TYPE_META[t].label }))].map((o) => (
          <button key={o.l} type="button" onClick={() => setParam({ type: o.v || null, page: null })}
            className={cn("rounded-full border px-3 py-1", type === o.v ? "border-primary bg-secondary text-primary font-medium" : "border-border")}>
            {o.l}
          </button>
        ))}
        {licensePending && (
          <button type="button" onClick={() => setParam({ license: null })} className="border-primary text-primary rounded-full border px-3 py-1">
            Licences to check ✕
          </button>
        )}
      </div>

      <div className="border-border mb-4 flex gap-1 overflow-x-auto overflow-y-hidden border-b [scrollbar-width:none]" role="tablist">
        {STATUS_TABS.map((t) => (
          <button key={t.value} type="button" role="tab" aria-selected={status === t.value}
            onClick={() => setParam({ status: t.value === "pending" ? null : t.value, page: null })}
            className={cn("-mb-px shrink-0 border-b-2 border-transparent px-3 py-2 text-xs", status === t.value ? "border-primary font-medium" : "text-muted-foreground hover:text-foreground")}>
            {t.label}
            {t.value !== "all" && <span className="text-muted-foreground tabular-nums"> ({counts[t.value] ?? 0})</span>}
          </button>
        ))}
      </div>

      <Input aria-label="Search providers" className="mb-4 max-w-md" placeholder="Name, phone, registration no., TIN or ID" value={query} onChange={(e) => setQuery(e.target.value)} />

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load providers"} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title="No providers here" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="py-2 pr-3 font-medium">Provider</th>
                <th className="py-2 pr-3 font-medium">Type</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Identity</th>
                <th className="py-2 pr-3 font-medium">Sector licence</th>
                <th className="py-2 pr-3 font-medium">Score</th>
                <th className="py-2 pr-3 font-medium">Jobs</th>
                <th className="py-2 font-medium">Joined</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} className="border-border border-t align-top">
                  <td className="py-2 pr-3">
                    <div className="flex items-center gap-2.5">
                      <ProviderAvatar name={p.display_name} photoUrl={p.photo_url} entity={p.entity_type} verified={p.status === "approved" ? verifiedLevel(p) : null} size="sm" />
                      <div className="min-w-0">
                        <Link href={`/marketplace/${p.id}`} className="font-medium hover:underline">{p.display_name}</Link>
                        {p.is_sample && <span className="ml-1 rounded bg-amber-100 px-1 text-[10px] text-amber-900">sample</span>}
                        <p className="text-muted-foreground text-[11px]">{p.registration_no ?? p.phone}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-2 pr-3">{TYPE_META[p.provider_type].label} · {p.entity_type === "company" ? "Company" : "Individual"}</td>
                  <td className="py-2 pr-3"><AgentStatusBadge status={p.status} /></td>
                  <td className="py-2 pr-3"><IdVerifiedBadge verified={p.id_verified} method={p.id_verification_method} /></td>
                  <td className="py-2 pr-3">
                    {p.external_license_no ? (
                      <span className={cn(p.external_license_status === "pending" && "font-medium text-amber-700", p.external_license_status === "verified" && "text-primary")}>
                        {p.external_license_status}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">none</span>
                    )}
                  </td>
                  <td className="py-2 pr-3"><ScoreBadge score={p.trust_score} /></td>
                  <td className="py-2 pr-3 tabular-nums">
                    {p.completed_count} done{p.open_jobs ? ` · ${p.open_jobs} open` : ""}
                    {p.open_disputes ? <span className="text-destructive"> · {p.open_disputes} complaint</span> : null}
                  </td>
                  <td className="text-muted-foreground py-2">{formatDate(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {total > PAGE_SIZE && (
            <div className="mt-4 flex items-center gap-3 text-xs">
              <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setParam({ page: String(page - 1) })}>Previous</Button>
              <span>Page {page + 1} of {Math.ceil(total / PAGE_SIZE)}</span>
              <Button size="sm" variant="outline" disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setParam({ page: String(page + 1) })}>Next</Button>
            </div>
          )}
        </div>
      )}
    </AdminPage>
  );
}
