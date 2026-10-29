"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  useAdminProviders,
  useMarketAction,
  useMarketStats,
  useSampleStatus,
  type AdminProviderSort,
} from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { useCan } from "@/modules/access/api";
import {
  AgentStatusBadge,
  EmptyState,
  ErrorState,
  IdVerifiedBadge,
  LoadingState,
  NativeSelect,
  formatDate,
  useDebounced,
} from "@cn/ui/guday/shared";
import { ScoreBadge } from "@cn/ui/marketplace/trust";
import { AREA_OPTIONS, TYPE_META, TYPE_ORDER } from "@cn/ui/marketplace/constants";
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
const SORTS: { value: AdminProviderSort; label: string }[] = [
  { value: "queue", label: "Waiting longest first" },
  { value: "newest", label: "Newest first" },
  { value: "score", label: "Highest score" },
  { value: "complaints", label: "Most open complaints" },
  { value: "expiry", label: "Licence ends soonest" },
];

/** "Remove sample data": never on the live site, never when sample providers have money records. */
function PurgeSamples() {
  const { can } = useCan();
  const { data } = useSampleStatus();
  const purge = useMarketAction<undefined, { providers_removed: number; hires_removed: number }>();
  const [confirm, setConfirm] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const status = data?.payload;
  if (!can("marketplace.maintenance") || !status || (!status.providers && !message)) return null;
  if (!status.can_purge && !message) {
    return <p className="text-muted-foreground max-w-xs text-[11px]">{status.reason}</p>;
  }
  return (
    <div className="flex flex-col items-end gap-1">
      {confirm ? (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="destructive" loading={purge.isPending}
            onClick={async () => {
              setMessage(null);
              try {
                const res = await purge.run(apiPaths.admin.marketPurgeSamples, MTD.POST);
                setMessage({ ok: true, text: `Removed ${res.providers_removed} sample providers and ${res.hires_removed} hires.` });
              } catch (err) {
                setMessage({ ok: false, text: getErrorMessage(err, "Could not remove the sample data") });
              }
              setConfirm(false);
            }}>
            Delete {status.providers} sample providers, their hires and reviews
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirm(false)}>Keep them</Button>
        </div>
      ) : status.can_purge ? (
        <Button size="sm" variant="outline" onClick={() => setConfirm(true)}>Remove sample data</Button>
      ) : null}
      {message && <p role={message.ok ? "status" : "alert"} className={cn("text-[11px]", !message.ok && "text-destructive")}>{message.text}</p>}
    </div>
  );
}

export function AdminProviders() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const rawStatus = params.get("status");
  const status = (STATUS_TABS.some((t) => t.value === rawStatus) ? rawStatus : "pending") as ProviderStatus | "all";
  const type = (TYPE_ORDER.includes(params.get("type") as ProviderType) ? params.get("type") : "") as ProviderType | "";
  const licensePending = params.get("license") === "pending";
  const expiring = params.get("expiring") === "30";
  const area = params.get("area") ?? "";
  const idUnverified = params.get("id") === "unverified";
  const sort = (SORTS.some((o) => o.value === params.get("sort")) ? params.get("sort") : "queue") as AdminProviderSort;
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(PAGE_SIZE);
  const [query, setQuery] = useState(params.get("q") ?? "");
  const q = useDebounced(query.trim(), 300);

  // Every filter change starts again at page 1
  const setParam = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(updates)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    next.delete("page");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== q) setParam({ q: q || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const stats = useMarketStats().data?.payload;
  const { data, isLoading, isError, error, refetch } = useAdminProviders({
    status: status === "all" || licensePending || expiring ? undefined : status,
    type: type || undefined,
    license_status: licensePending ? "pending" : undefined,
    expiring: expiring ? 30 : undefined,
    area: area || undefined,
    id_verified: idUnverified ? false : undefined,
    sort,
    q: q || undefined,
    limit: size,
    offset: page * size,
  });
  const items = data?.payload.items ?? [];
  const total = data?.payload.total ?? 0;
  const counts = stats?.agents ?? {};

  return (
    <AdminPage
      title="Marketplace providers · አገልግሎት ሰጪዎች"
      description="Guday Geday agents and agencies. Approve applications, check sector licences and watch trust scores."
      actions={<PurgeSamples />}
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
          <button key={o.l} type="button" onClick={() => setParam({ type: o.v || null })}
            className={cn("rounded-full border px-3 py-1", type === o.v ? "border-primary bg-secondary text-primary font-medium" : "border-border")}>
            {o.l}
          </button>
        ))}
        {licensePending && (
          <button type="button" onClick={() => setParam({ license: null })} className="border-primary text-primary rounded-full border px-3 py-1">
            Licences to check ✕
          </button>
        )}
        <button type="button" aria-pressed={expiring} onClick={() => setParam({ expiring: expiring ? null : "30" })}
          className={cn("rounded-full border px-3 py-1", expiring ? "border-primary bg-secondary text-primary font-medium" : "border-border")}>
          Licence ends within 30 days
        </button>
        <button type="button" aria-pressed={idUnverified} onClick={() => setParam({ id: idUnverified ? null : "unverified" })}
          className={cn("rounded-full border px-3 py-1", idUnverified ? "border-primary bg-secondary text-primary font-medium" : "border-border")}>
          ID not verified
        </button>
      </div>

      <div className="border-border mb-4 flex gap-1 overflow-x-auto overflow-y-hidden border-b [scrollbar-width:none]" role="tablist">
        {STATUS_TABS.map((t) => (
          <button key={t.value} type="button" role="tab" aria-selected={status === t.value}
            onClick={() => setParam({ status: t.value === "pending" ? null : t.value })}
            className={cn("-mb-px shrink-0 border-b-2 border-transparent px-3 py-2 text-xs", status === t.value ? "border-primary font-medium" : "text-muted-foreground hover:text-foreground")}>
            {t.label}
            {t.value !== "all" && <span className="text-muted-foreground tabular-nums"> ({counts[t.value] ?? 0})</span>}
          </button>
        ))}
      </div>

      <div className="mb-4 grid gap-2 text-xs sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <Input aria-label="Search providers" placeholder="Name, phone, registration no., TIN or ID" value={query} onChange={(e) => setQuery(e.target.value)} />
        <NativeSelect aria-label="Area" value={area} onChange={(e) => setParam({ area: e.target.value || null })}>
          <option value="">Any area</option>
          {AREA_OPTIONS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
        </NativeSelect>
        <NativeSelect aria-label="Sort" value={sort} onChange={(e) => setParam({ sort: e.target.value === "queue" ? null : e.target.value })}>
          {SORTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </NativeSelect>
      </div>

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
                    {p.has_external_license ? (
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
        </div>
      )}
      <Pager page={page} pageSize={size} total={total} onPage={setPage} onPageSize={setSize} />
    </AdminPage>
  );
}
