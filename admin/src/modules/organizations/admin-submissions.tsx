"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { ADMIN_ORGS_PAGE_SIZE, useReviewSubmission, useSubmission, useSubmissions } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { Textarea } from "@cn/ui/textarea";
import { siteUrl } from "@cn/core/config/env";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { timeAgo } from "@cn/core/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { StatusBadge } from "@/modules/shared/status-badge";
import { useDebounced } from "@cn/ui/guday/shared";
import { CompletenessMeter, OrgStatusChip } from "@cn/ui/organizations/shared";
import { URL_PATTERN, collectLinks, diffSnapshots, hostOf } from "./snapshot-diff";
import { useUrlParams } from "./use-url-param";

const TABS = [
  { value: "pending", label: "Waiting for review" },
  { value: "scheduled", label: "Scheduled" },
  { value: "changes_requested", label: "Changes requested" },
  { value: "published", label: "Published" },
  { value: "superseded", label: "Replaced by a newer one" },
  { value: "all", label: "All" },
];

export function AdminSubmissions() {
  const [{ status, q: urlQ }, setFilters] = useUrlParams({ status: "pending", q: "" });
  const [query, setQuery] = useState(urlQ);
  const q = useDebounced(query.trim(), 300);
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(ADMIN_ORGS_PAGE_SIZE);
  const { payload, isLoading, error, refetch } = useSubmissions(status, page, urlQ, size);
  const items = payload?.submissions ?? [];

  useEffect(() => {
    if (q !== urlQ) setFilters({ q });
    // Only react to typing; a URL change (Back) must not be undone by the old input value
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  return (
    <AdminPage
      title="Service submissions"
      description="New services and changes submitted by organizations. Nothing reaches the public, the paths or the knowledge graph until you publish it."
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
      <Input
        className="mb-4 max-w-sm"
        placeholder="Search service, organization or change"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Search submissions"
      />
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} error={error} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title="Nothing here" />
      ) : (
        <ul className="ring-foreground/10 bg-card divide-border divide-y text-sm ring-1">
          {items.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <div className="min-w-0">
                <p className="font-medium break-words">
                  {s.service_name}{" "}
                  <span className="text-muted-foreground text-xs font-normal">{s.is_update ? "· update to a live service" : "· new service"}</span>
                </p>
                <p className="text-muted-foreground text-xs break-words">
                  {s.org_name} · submitted {timeAgo(s.created_at)} by {s.submitted_by}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={s.status.replace("_", " ")} tone={s.status === "pending" ? "warning" : s.status === "published" ? "good" : "neutral"} />
                <Link href={`/submissions/${s.id}`}>
                  <Button size="sm" variant="outline">
                    Open
                  </Button>
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
    </AdminPage>
  );
}

/** A full URL with the website name in bold, so a look-alike domain stands out. */
function UrlText({ url }: { url: string }) {
  if (url.startsWith("/uploads/public/")) {
    return (
      <a href={`${siteUrl}${url}`} target="_blank" rel="noopener noreferrer" className="underline">
        Uploaded to our site: {url}
      </a>
    );
  }
  const host = hostOf(url);
  if (!host) return <span>{url}</span>;
  const i = url.toLowerCase().indexOf(host);
  const [start, rest] = i >= 0 ? [url.slice(0, i), url.slice(i + host.length)] : ["", url];
  return (
    <a href={url} target="_blank" rel="noopener noreferrer nofollow" className="break-all underline">
      <span className="text-muted-foreground">{start}</span>
      <strong className={cn(host.includes("xn--") && "text-destructive")}>{i >= 0 ? url.slice(i, i + host.length) : host}</strong>
      <span>{rest}</span>
    </a>
  );
}

/** Text with any links in it rendered by UrlText. */
function LineText({ text }: { text: string }) {
  const parts = text.split(URL_PATTERN);
  return (
    <>
      {parts.map((p, i) => (i % 2 === 1 ? <UrlText key={i} url={p} /> : <span key={i}>{p}</span>))}
    </>
  );
}

function Lines({ lines }: { lines: string[] }) {
  if (!lines.length) return <span className="text-muted-foreground">-</span>;
  return (
    <ul className="space-y-0.5">
      {lines.map((l, i) => (
        <li key={i} className="break-words">
          <LineText text={l} />
        </li>
      ))}
    </ul>
  );
}

/** What already happened to a submission that is no longer waiting, in plain words: [what, then, show who decided]. */
const DECIDED: Record<string, [string, string, boolean]> = {
  published: ["Published", "", true],
  scheduled: ["Approved", " It goes live on its start date.", true],
  changes_requested: ["Sent back to the organization for changes", "", true],
  superseded: ["Replaced by a newer submission from the organization", "", false],
};

export function AdminSubmissionDetail({ id }: { id: string }) {
  const { payload, isLoading, error, refetch } = useSubmission(id);
  const { review, isPending } = useReviewSubmission();
  const [note, setNote] = useState("");
  const [onlyChanged, setOnlyChanged] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const noteId = useId();
  const sub = payload?.submission;

  if (isLoading) return <AdminPage title="Submission"><LoadingState /></AdminPage>;
  if (error || !sub) {
    return (
      <AdminPage title="Submission">
        <ErrorState message={getErrorMessage(error, "Not found")} error={error} onRetry={() => refetch()} />
      </AdminPage>
    );
  }

  const decided = DECIDED[sub.status] ?? ["Already decided", "", true];
  const ctx = { branches: sub.branch_names ?? {}, services: sub.service_names ?? {} };
  const isUpdate = !!sub.published_snapshot;
  const rows = diffSnapshots(sub.published_snapshot as Record<string, unknown> | null, sub.snapshot as Record<string, unknown>, ctx);
  const changed = rows.filter((r) => r.changed);
  const shown = isUpdate && onlyChanged ? changed : rows.filter((r) => r.after.length || r.before.length);
  const liveHosts = new Set(collectLinks(sub.published_snapshot as Record<string, unknown> | null).map((l) => hostOf(l.url)).filter(Boolean));
  const links = collectLinks(sub.snapshot as Record<string, unknown>);

  return (
    <AdminPage
      title={sub.snapshot.name}
      description={`${sub.org_name} · submitted ${timeAgo(sub.created_at)} by ${sub.submitted_by ?? "unknown"}`}
    >
      <Link href="/submissions" className="text-primary mb-4 inline-block text-xs hover:underline">
        ← All submissions
      </Link>
      <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
        <StatusBadge status={sub.status.replace("_", " ")} tone={sub.status === "pending" ? "warning" : "neutral"} />
        {sub.org_status && <OrgStatusChip status={sub.org_status} />}
        <span className="text-muted-foreground">
          {isUpdate ? `${changed.length} field${changed.length === 1 ? "" : "s"} changed since version ${sub.version}` : "New service, never published"}
        </span>
      </div>

      {sub.change_summary && (
        <div className="mb-4 rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950">
          <p className="font-semibold">What changed, according to the organization</p>
          <p>{sub.change_summary}</p>
          {sub.change_reason && <p className="text-xs">Reason: {sub.change_reason}</p>}
          <p className="text-xs">
            {sub.effective_at ? `Takes effect ${sub.effective_at}. Publishing schedules it for that date.` : "Takes effect as soon as it is published."}
          </p>
        </div>
      )}
      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-4">
          {links.length > 0 && (
            <section className="ring-foreground/10 bg-card p-3 text-xs ring-1">
              <h2 className="mb-1 font-semibold">Links people will follow</h2>
              <p className="text-muted-foreground mb-2">
                Check each website name. A name that is new for this service, or contains xn-- (letters from another alphabet), needs a closer look.
              </p>
              <ul className="space-y-1">
                {links.map((l, i) => {
                  const host = hostOf(l.url);
                  const isNew = isUpdate && host && !liveHosts.has(host);
                  return (
                    <li key={i} className="break-words">
                      <span className="text-muted-foreground">{l.field}: </span>
                      <UrlText url={l.url} />
                      {isNew && <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">new website</span>}
                      {l.url.startsWith("http://") && <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">not secure (http)</span>}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
          {isUpdate && (
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} />
              Show only changed fields
            </label>
          )}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-xs">
              <thead className="text-muted-foreground text-[11px]">
                <tr>
                  <th className="w-40 py-2 pr-3 font-medium">Field</th>
                  {isUpdate && <th className="py-2 pr-3 font-medium">Live now</th>}
                  <th className="py-2 font-medium">Submitted</th>
                </tr>
              </thead>
              <tbody>
                {shown.length === 0 && (
                  <tr>
                    <td colSpan={3} className="text-muted-foreground py-3">
                      No field differs from the live version.
                    </td>
                  </tr>
                )}
                {shown.map((r) => (
                  <tr key={r.key} className={cn("border-border border-t align-top", r.changed && "bg-amber-50 dark:bg-amber-950/30")}>
                    <td className="py-2 pr-3 font-medium">
                      {r.label}
                      {r.changed && (
                        <span className="ml-1 text-amber-700" aria-label="changed">
                          ●
                        </span>
                      )}
                    </td>
                    {isUpdate && (
                      <td className="text-muted-foreground py-2 pr-3">
                        <Lines lines={r.before} />
                      </td>
                    )}
                    <td className="py-2">
                      <Lines lines={r.after} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="ring-foreground/10 bg-card h-fit space-y-3 p-4 ring-1">
          <h2 className="font-semibold">Path data</h2>
          <CompletenessMeter completeness={sub.completeness} />
          <h2 className="pt-2 font-semibold">Decision</h2>
          {sub.status !== "pending" ? (
            <p className="text-muted-foreground text-xs">
              {decided[0]}
              {decided[2] && sub.reviewed_by && ` by ${sub.reviewed_by}`}.{decided[1]}
              {sub.admin_note && ` Note to the organization: ${sub.admin_note}`}
            </p>
          ) : (
            <>
              {sub.org_status !== "verified" && (
                <p className="text-xs text-amber-800">
                  Verify the organization before publishing.{" "}
                  <Link href={`/organizations/${sub.org_id}`} className="underline">
                    Open organization
                  </Link>
                </p>
              )}
              <div className="space-y-1">
                <label htmlFor={noteId} className="text-muted-foreground text-[11px]">
                  Note to the organization (required to request changes)
                </label>
                <Textarea id={noteId} rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={isPending || sub.org_status !== "verified" || sub.completeness.core_missing.length > 0}
                  onClick={async () => {
                    setErr(null);
                    try {
                      await review(sub.id, { action: "publish", note: note.trim() || undefined });
                    } catch (e) {
                      setErr(getErrorMessage(e));
                    }
                  }}
                >
                  {sub.effective_at ? "Approve and schedule" : "Publish"}
                </Button>
                <Button
                  variant="outline"
                  disabled={isPending || !note.trim()}
                  onClick={async () => {
                    setErr(null);
                    try {
                      await review(sub.id, { action: "request_changes", note: note.trim() });
                    } catch (e) {
                      setErr(getErrorMessage(e));
                    }
                  }}
                >
                  Request changes
                </Button>
              </div>
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
