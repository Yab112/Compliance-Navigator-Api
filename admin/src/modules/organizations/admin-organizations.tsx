"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import {
  ADMIN_ORGS_PAGE_SIZE,
  downloadOrganizationsCsv,
  useAdminOrganization,
  useAdminOrganizations,
  useReviewOrganization,
} from "@cn/core/api/organizations";
import { useAdminQuery } from "@cn/core/api/admin";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { PrivateFileButton } from "@/modules/marketplace/private-document";
import { formatDate, timeAgo } from "@cn/core/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { NativeSelect } from "@/modules/shared/native-select";
import { useDebounced } from "@cn/ui/guday/shared";
import { OrgLogo, OrgStatusChip, OrgTypeLabel, ServiceStatusChip } from "@cn/ui/organizations/shared";
import type { CatalogInstitution } from "@cn/core/types/catalog";
import type { AdminOrganization } from "@cn/core/types/organizations";
import { useCan } from "@/modules/access/api";
import { useUrlParams } from "./use-url-param";

const TABS = [
  { value: "pending", label: "Pending verification" },
  { value: "verified", label: "Verified" },
  { value: "suspended", label: "Suspended" },
  { value: "rejected", label: "Rejected" },
  { value: "draft", label: "Registration not finished" },
  { value: "all", label: "All" },
];

export function AdminOrganizations() {
  const [{ status, q: urlQ }, setFilters] = useUrlParams({ status: "pending", q: "" });
  const [query, setQuery] = useState(urlQ);
  const q = useDebounced(query.trim(), 300);
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(ADMIN_ORGS_PAGE_SIZE);
  const { payload, isLoading, error, refetch } = useAdminOrganizations(status, urlQ, page, size);
  const [exportState, setExportState] = useState<{ busy: boolean; error?: string }>({ busy: false });
  const days = payload?.confirm_every_days ?? 90;

  // Typing updates the URL once the user pauses, so Back and refresh keep the search
  useEffect(() => {
    if (q !== urlQ) setFilters({ q });
    // Only react to typing; a URL change (Back) must not be undone by the old input value
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  return (
    <AdminPage
      title="Organizations · ተቋማት"
      description="Organizations that registered to publish their services. Verify that the representative may speak for the organization before its services can go live."
    >
      <div className="mb-4 flex flex-wrap gap-1" role="group" aria-label="Filter by status">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            aria-pressed={status === t.value}
            onClick={() => setFilters({ status: t.value })}
            className={cn("rounded px-3 py-1.5 text-xs", status === t.value ? "bg-primary text-primary-foreground" : "bg-muted")}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mb-4 flex flex-wrap items-start gap-2">
        <Input
          className="max-w-sm"
          placeholder="Search name or official email"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search organizations"
        />
        <div>
          <Button
            variant="outline"
            loading={exportState.busy}
            onClick={async () => {
              setExportState({ busy: true });
              try {
                await downloadOrganizationsCsv(status, urlQ);
                setExportState({ busy: false });
              } catch (e) {
                setExportState({ busy: false, error: getErrorMessage(e, "Couldn't export the list") });
              }
            }}
          >
            Export CSV
          </Button>
          {exportState.error && (
            <p role="alert" className="text-destructive mt-1 text-xs">
              {exportState.error}
            </p>
          )}
        </div>
      </div>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} error={error} onRetry={() => refetch()} />
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
                <th className="py-2 pr-3 text-right font-medium">Not confirmed {days} days</th>
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
                    {!o.has_authorization_letter && <p className="mt-1 text-[11px] text-amber-800">No letter</p>}
                  </td>
                  <td className="py-2 pr-3">
                    <p>{o.representative_name}</p>
                    <p className="text-muted-foreground text-[11px]">{o.official_email}</p>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{o.live_services ?? 0}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{o.completeness == null ? "-" : `${o.completeness}%`}</td>
                  <td className={cn("py-2 pr-3 text-right tabular-nums", (o.services_due ?? 0) > 0 && "font-semibold text-amber-700")}>{o.services_due ?? 0}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {(o.open_reports ?? 0) > 0 ? (
                      <Link href={`/feedback?org_id=${o.id}`} className="font-semibold text-amber-700 underline">
                        {o.open_reports}
                      </Link>
                    ) : (
                      0
                    )}
                  </td>
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
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
    </AdminPage>
  );
}

type Action = { action: string; label: string; needsNote: boolean; needsLetter?: boolean; confirm?: string };

const ACTIONS: Record<string, Action[]> = {
  pending: [
    { action: "verify", label: "Verify", needsNote: false, needsLetter: true },
    { action: "reject", label: "Reject", needsNote: true },
  ],
  rejected: [{ action: "verify", label: "Verify", needsNote: false, needsLetter: true }],
  verified: [
    {
      action: "suspend",
      label: "Suspend",
      needsNote: true,
      confirm: "Suspending hides every live service of this organization from the public and from paths until you reinstate it.",
    },
  ],
  suspended: [{ action: "reinstate", label: "Reinstate", needsNote: false, needsLetter: true }],
};

const hostOf = (value?: string | null) => {
  if (!value) return null;
  try {
    return new URL(value.includes("://") ? value : `https://${value}`).hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return null;
  }
};

/** True when the official email's domain is not the website's domain or one of its subdomains. */
function emailDomainDiffers(org: AdminOrganization) {
  const site = hostOf(org.website);
  const mail = org.official_email?.split("@")[1]?.toLowerCase();
  if (!site || !mail) return false;
  return !(mail === site || mail.endsWith(`.${site}`) || site.endsWith(`.${mail}`));
}

export function AdminOrganizationDetail({ id }: { id: string }) {
  const { payload, isLoading, error, refetch } = useAdminOrganization(id);
  const { review, isPending } = useReviewOrganization();
  // Viewing needs organizations.view; verifying, rejecting and suspending need organizations.review
  const { can, loaded: permsLoaded } = useCan();
  const canReview = can("organizations.review");
  const institutions = useAdminQuery<{ institutions: CatalogInstitution[] }>(["catalog-institutions"], apiPaths.catalog.institutions);
  const [note, setNote] = useState("");
  const [institution, setInstitution] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const noteId = useId();
  const instId = useId();
  const org = payload?.organization;

  if (isLoading) return <AdminPage title="Organization"><LoadingState /></AdminPage>;
  if (error || !org) {
    return (
      <AdminPage title="Organization">
        <ErrorState message={getErrorMessage(error, "Not found")} error={error} onRetry={() => refetch()} />
      </AdminPage>
    );
  }

  const actions = ACTIONS[org.status] ?? [];
  const hasLetter = !!org.authorization_letter_key;
  const chosenInstitution = institution ?? org.catalog_institution_id ?? "";
  const institutionName = (institutions.payload?.institutions ?? []).find((i) => i.id === org.catalog_institution_id)?.name;
  const confirmAction = actions.find((x) => x.action === confirming);

  const run = async (a: Action) => {
    setErr(null);
    try {
      await review(org.id, {
        action: a.action,
        note: note.trim() || undefined,
        catalog_institution_id: institution && institution !== org.catalog_institution_id ? institution : undefined,
      });
      setNote("");
      setInstitution(null);
      setConfirming(null);
    } catch (e) {
      setErr(getErrorMessage(e));
    }
  };

  return (
    <AdminPage title={org.name} description={org.name_am ?? undefined}>
      <Link href="/organizations" className="text-primary mb-4 inline-block text-xs hover:underline">
        ← All organizations
      </Link>
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-6 text-sm">
          <section className="ring-foreground/10 bg-card space-y-2 p-4 ring-1">
            <div className="flex flex-wrap items-center gap-2">
              <OrgStatusChip status={org.status} />
              <OrgTypeLabel type={org.org_type} />
              {org.catalog_institution_id && (
                <span className="text-muted-foreground text-xs">Matches MESOB institution {institutionName ?? org.catalog_institution_id}</span>
              )}
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
                <div key={k} className="min-w-0">
                  <dt className="text-muted-foreground text-[11px]">{k}</dt>
                  <dd className="break-words">{v || "-"}</dd>
                </div>
              ))}
            </dl>
            {emailDomainDiffers(org) && (
              <p className="text-xs text-amber-800">
                The official email ({org.official_email?.split("@")[1]}) is not on the website&apos;s domain ({hostOf(org.website)}). Check that the
                representative really works there.
              </p>
            )}
            {org.authorization_letter_key ? (
              <PrivateFileButton fileKey={org.authorization_letter_key} label="Open authorization letter" />
            ) : (
              <p className="text-xs text-amber-800">No authorization letter uploaded. The organization can&apos;t be verified until it uploads one.</p>
            )}
          </section>

          <section>
            <h2 className="mb-2 font-semibold">Services</h2>
            {!org.services?.length ? (
              <p className="text-muted-foreground text-xs">No services yet.</p>
            ) : (
              <ul className="ring-foreground/10 divide-border bg-card divide-y ring-1">
                {org.services.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-2 p-3">
                    <span className="min-w-0 break-words">{s.name}</span>
                    <ServiceStatusChip status={s.status} isLive={s.is_live} />
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 flex flex-wrap gap-3 text-xs">
              <Link href={`/submissions?q=${encodeURIComponent(org.name)}&status=all`} className="text-primary hover:underline">
                Submissions from this organization
              </Link>
              <Link href={`/feedback?org_id=${org.id}&status=all`} className="text-primary hover:underline">
                Reports about its services
              </Link>
            </p>
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
                <li key={m.id} className="break-words">
                  {m.email} · {m.role}
                  {!m.accepted && " (invited, not accepted yet)"}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-2 font-semibold">History</h2>
            <ul className="space-y-1 text-xs">
              {org.events?.map((e, i) => (
                <li key={i} className="break-words">
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
          {!canReview ? (
            permsLoaded && (
              <p className="text-muted-foreground text-xs">
                You can see this organization but not verify, reject or suspend it. That needs the &quot;Review organizations&quot; permission.
              </p>
            )
          ) : (
            <>
              <div className="space-y-1">
                <label htmlFor={instId} className="text-muted-foreground text-[11px]">
                  Matching MESOB institution (optional)
                </label>
                <NativeSelect id={instId} className="w-full" value={chosenInstitution} onChange={(e) => setInstitution(e.target.value)}>
                  <option value="">Not matched</option>
                  {(institutions.payload?.institutions ?? []).map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                      {i.short_name ? ` (${i.short_name})` : ""}
                    </option>
                  ))}
                </NativeSelect>
                <p className="text-muted-foreground text-[11px]">Saved with your next decision.</p>
              </div>
              <div className="space-y-1">
                <label htmlFor={noteId} className="text-muted-foreground text-[11px]">
                  Note to the organization (required to reject or suspend)
                </label>
                <Textarea id={noteId} rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
              </div>
              {confirmAction ? (
                <div role="alertdialog" aria-label={`Confirm ${confirmAction.label.toLowerCase()}`} className="space-y-2 border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950">
                  <p>{confirmAction.confirm}</p>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="destructive" disabled={isPending || !note.trim()} onClick={() => void run(confirmAction)}>
                      Yes, {confirmAction.label.toLowerCase()}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setConfirming(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {actions.map((a) => (
                    <Button
                      key={a.action}
                      variant={a.needsNote ? "outline" : "default"}
                      disabled={isPending || (a.needsNote && !note.trim()) || (a.needsLetter && !hasLetter)}
                      onClick={() => (a.confirm ? setConfirming(a.action) : void run(a))}
                    >
                      {a.label}
                    </Button>
                  ))}
                </div>
              )}
              {!hasLetter && actions.some((a) => a.needsLetter) && (
                <p className="text-xs text-amber-800">Verifying needs an authorization letter. Reject with a note asking for one.</p>
              )}
              <p className="text-muted-foreground text-[11px]">The organization&apos;s team gets a notification with your decision and note.</p>
              {err && (
                <p role="alert" className="text-destructive text-xs">
                  {err}
                </p>
              )}
            </>
          )}
        </aside>
      </div>
    </AdminPage>
  );
}
