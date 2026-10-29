"use client";

import Link from "next/link";
import { useState } from "react";
import { ADMIN_ORGS_PAGE_SIZE, useAdminOrganization, useAdminOrganizations, useReviewOrganization } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { Textarea } from "@cn/ui/textarea";
import { api } from "@cn/core/lib/api";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { formatDate, timeAgo } from "@cn/core/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { useDebounced } from "@cn/ui/guday/shared";
import { OrgLogo, OrgStatusChip, OrgTypeLabel, ServiceStatusChip } from "@cn/ui/organizations/shared";

const TABS = [
  { value: "pending", label: "Pending verification" },
  { value: "verified", label: "Verified" },
  { value: "suspended", label: "Suspended" },
  { value: "rejected", label: "Rejected" },
  { value: "draft", label: "Registration not finished" },
  { value: "all", label: "All" },
];

export function AdminOrganizations() {
  const [status, setStatus] = useState("pending");
  const [query, setQuery] = useState("");
  const q = useDebounced(query.trim(), 300);
  const [page, setPage] = useUrlPage();
  const { payload, isLoading, error, refetch } = useAdminOrganizations(status, q, page);

  return (
    <AdminPage
      title="Organizations · ተቋማት"
      description="Organizations that registered to publish their services. Verify that the representative may speak for the organization before its services can go live."
    >
      <div className="mb-4 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => {
              setStatus(t.value);
              if (page) setPage(0);
            }}
            className={cn("rounded px-3 py-1.5 text-xs", status === t.value ? "bg-primary text-primary-foreground" : "bg-muted")}
          >
            {t.label}
          </button>
        ))}
      </div>
      <Input
        className="mb-4 max-w-sm"
        placeholder="Search name or official email"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          if (page) setPage(0);
        }}
        aria-label="Search organizations"
      />
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !payload?.items.length ? (
        <EmptyState title="No organizations here" />
      ) : (
        <div className="overflow-x-auto">
          <p className="text-muted-foreground mb-2 text-xs">
            {payload.total} organization{payload.total === 1 ? "" : "s"}
          </p>
          <table className="w-full min-w-[980px] text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="py-2 pr-3 font-medium">Organization</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Representative</th>
                <th className="py-2 pr-3 text-right font-medium">Live services</th>
                <th className="py-2 pr-3 text-right font-medium">Data filled</th>
                <th className="py-2 pr-3 text-right font-medium">Not confirmed 90 days</th>
                <th className="py-2 pr-3 text-right font-medium">Open reports</th>
                <th className="py-2 pr-3 font-medium">Registered</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {payload.items.map((o) => (
                <tr key={o.id} className="border-border border-t align-top">
                  <td className="py-2 pr-3">
                    <div className="flex items-center gap-2">
                      <OrgLogo name={o.name} url={o.logo_url} className="size-8 text-[10px]" />
                      <div>
                        <p className="font-medium">{o.name}</p>
                        <OrgTypeLabel type={o.org_type} className="text-[11px]" />
                      </div>
                    </div>
                  </td>
                  <td className="py-2 pr-3">
                    <OrgStatusChip status={o.status} />
                  </td>
                  <td className="py-2 pr-3">
                    <p>{o.representative_name}</p>
                    <p className="text-muted-foreground text-[11px]">{o.official_email}</p>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{o.live_services ?? 0}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{o.completeness == null ? "-" : `${o.completeness}%`}</td>
                  <td className={cn("py-2 pr-3 text-right tabular-nums", (o.services_due ?? 0) > 0 && "font-semibold text-amber-700")}>{o.services_due ?? 0}</td>
                  <td className={cn("py-2 pr-3 text-right tabular-nums", (o.open_reports ?? 0) > 0 && "font-semibold text-amber-700")}>{o.open_reports ?? 0}</td>
                  <td className="text-muted-foreground py-2 pr-3">{timeAgo(o.created_at)}</td>
                  <td className="py-2 text-right">
                    <Link href={`/organizations/${o.id}`}>
                      <Button size="sm" variant="outline">
                        Review
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={page} pageSize={ADMIN_ORGS_PAGE_SIZE} total={payload?.total ?? 0} onPage={setPage} />
    </AdminPage>
  );
}

const ACTIONS: Record<string, { action: string; label: string; needsNote: boolean }[]> = {
  pending: [
    { action: "verify", label: "Verify", needsNote: false },
    { action: "reject", label: "Reject", needsNote: true },
  ],
  rejected: [{ action: "verify", label: "Verify", needsNote: false }],
  verified: [{ action: "suspend", label: "Suspend", needsNote: true }],
  suspended: [{ action: "reinstate", label: "Reinstate", needsNote: false }],
};

export function AdminOrganizationDetail({ id }: { id: string }) {
  const { payload, isLoading, error, refetch } = useAdminOrganization(id);
  const { review, isPending } = useReviewOrganization();
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const org = payload?.organization;

  if (isLoading) return <AdminPage title="Organization"><LoadingState /></AdminPage>;
  if (error || !org) {
    return (
      <AdminPage title="Organization">
        <ErrorState message={getErrorMessage(error, "Not found")} onRetry={() => refetch()} />
      </AdminPage>
    );
  }

  return (
    <AdminPage title={org.name} description={org.name_am ?? undefined}>
      <Link href="/organizations" className="text-primary mb-4 inline-block text-xs hover:underline">
        ← All organizations
      </Link>
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6 text-sm">
          <section className="ring-foreground/10 bg-card space-y-2 p-4 ring-1">
            <div className="flex flex-wrap items-center gap-2">
              <OrgStatusChip status={org.status} />
              <OrgTypeLabel type={org.org_type} />
              {org.catalog_institution_id && <span className="text-muted-foreground text-xs">Matches MESOB institution {org.catalog_institution_id}</span>}
            </div>
            {org.description && <p>{org.description}</p>}
            <dl className="grid gap-2 sm:grid-cols-2">
              {[
                ["Representative", `${org.representative_name ?? "-"}, ${org.representative_title ?? "-"}`],
                ["Official email", org.official_email],
                ["Registered by", org.created_by_email],
                ["Public phone", org.phone],
                ["Public email", org.email],
                ["Website", org.website],
                ["Address", org.hq_address],
                ["Registered", formatDate(org.created_at)],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-muted-foreground text-[11px]">{k}</dt>
                  <dd>{v || "-"}</dd>
                </div>
              ))}
            </dl>
            {org.authorization_letter_key ? (
              <PrivateFileButton fileKey={org.authorization_letter_key} label="Open authorization letter" />
            ) : (
              <p className="text-xs text-amber-800">No authorization letter uploaded.</p>
            )}
          </section>

          <section>
            <h2 className="mb-2 font-semibold">Services</h2>
            {!org.services?.length ? (
              <p className="text-muted-foreground text-xs">No services yet.</p>
            ) : (
              <ul className="ring-foreground/10 divide-border bg-card divide-y ring-1">
                {org.services.map((s) => (
                  <li key={s.id} className="flex items-center justify-between p-3">
                    <span>{s.name}</span>
                    <ServiceStatusChip status={s.status} isLive={s.is_live} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-2 font-semibold">Branches and team</h2>
            <ul className="text-xs">
              {org.branches?.map((b) => (
                <li key={b.id}>
                  {b.name} · {[b.sub_city, b.address].filter(Boolean).join(", ")}
                </li>
              ))}
            </ul>
            <ul className="mt-2 text-xs">
              {org.members?.map((m) => (
                <li key={m.id}>
                  {m.email} · {m.role}
                  {!m.accepted && " (invited)"}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-2 font-semibold">History</h2>
            <ul className="space-y-1 text-xs">
              {org.events?.map((e, i) => (
                <li key={i}>
                  <span className="text-muted-foreground">{timeAgo(e.created_at)}</span> · {e.action.replace(/_/g, " ")}
                  {e.actor && ` by ${e.actor}`}
                  {e.note && `: ${e.note}`}
                </li>
              ))}
            </ul>
          </section>
        </div>

        <aside className="ring-foreground/10 bg-card h-fit space-y-3 p-4 ring-1">
          <h2 className="font-semibold">Decision</h2>
          {org.verification_note && <p className="text-muted-foreground text-xs">Last note: {org.verification_note}</p>}
          <Textarea rows={3} placeholder="Note to the organization (required to reject or suspend)" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex flex-wrap gap-2">
            {(ACTIONS[org.status] ?? []).map((a) => (
              <Button
                key={a.action}
                variant={a.needsNote ? "outline" : "default"}
                disabled={isPending || (a.needsNote && !note.trim())}
                onClick={async () => {
                  setErr(null);
                  try {
                    await review(org.id, { action: a.action, note: note.trim() || undefined });
                    setNote("");
                  } catch (e) {
                    setErr(getErrorMessage(e));
                  }
                }}
              >
                {a.label}
              </Button>
            ))}
          </div>
          {err && <p className="text-destructive text-xs">{err}</p>}
        </aside>
      </div>
    </AdminPage>
  );
}

/** Private uploads need the admin's token, so fetch them and open the blob. */
function PrivateFileButton({ fileKey, label }: { fileKey: string; label: string }) {
  const [err, setErr] = useState<string | null>(null);
  return (
    <div>
      <button
        type="button"
        className="text-primary text-xs font-medium hover:underline"
        onClick={async () => {
          setErr(null);
          try {
            const res = await api.get(`/${apiPaths.admin.file}`, { params: { key: fileKey }, responseType: "blob" });
            window.open(URL.createObjectURL(res.data as Blob), "_blank", "noopener");
          } catch (e) {
            setErr(getErrorMessage(e, "Could not open the file"));
          }
        }}
      >
        {label} ↗
      </button>
      {err && <p className="text-destructive text-xs">{err}</p>}
    </div>
  );
}
