"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { FEEDBACK_PAGE_SIZE, useFeedbackFlags, useResolveFlag } from "@cn/core/api/admin";
import { siteUrl } from "@cn/core/config/env";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { formatDateTime, humanize } from "@cn/core/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { NativeSelect } from "@/modules/shared/native-select";
import { StatusBadge } from "@/modules/shared/status-badge";
import { useDebounced } from "@cn/ui/guday/shared";
import { useUrlParams } from "@/modules/organizations/use-url-param";
import type { FeedbackFlag, FeedbackFlagEvent } from "@cn/core/types/admin";

const TABS = [
  { value: "open", label: "Open" },
  { value: "org_responded", label: "Organization answered" },
  { value: "resolved", label: "Resolved" },
  { value: "dismissed", label: "Dismissed" },
  { value: "all", label: "All" },
];

const TARGET_TYPES = ["document", "gov_service", "office", "agent", "roadmap_step", "org_service", "other"];

const EVENT_LABEL: Record<FeedbackFlagEvent["action"], string> = {
  created: "Reported",
  org_responded: "Organization answered",
  resolved: "Resolved",
  dismissed: "Dismissed",
  reopened: "Reopened",
};

function targetLink(flag: FeedbackFlag): { href: string; external?: boolean } | null {
  if (flag.target_type === "org_service" && flag.org_id) return { href: `/organizations/${flag.org_id}` };
  if (!flag.target_id) return null;
  if (flag.target_type === "document" || flag.target_type === "roadmap_step") return { href: "/graph" };
  // Catalog services have no staff page; open the public page people saw
  if (flag.target_type === "gov_service") return { href: `${siteUrl}/services/${encodeURIComponent(flag.target_id)}`, external: true };
  if (flag.target_type === "agent") return { href: `/marketplace/${flag.target_id}` };
  return null;
}

function FlagItem({ flag }: { flag: FeedbackFlag }) {
  const { resolveFlag, isPending } = useResolveFlag();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const noteId = useId();
  const link = targetLink(flag);

  const act = async (status: string) => {
    setError(null);
    try {
      await resolveFlag(flag.id, status, note.trim() || undefined);
      setNote("");
    } catch (e) {
      setError(getErrorMessage(e, "Couldn't update the report"));
    }
  };

  return (
    <li className="border-border space-y-2 border p-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-muted-foreground flex min-w-0 flex-wrap items-center gap-x-2 text-[11px]">
          <span className="text-foreground font-medium">{humanize(flag.target_type)}</span>
          {flag.org_name && <span className="text-foreground">{flag.org_name}</span>}
          {(flag.target_id || link) &&
            (link ? (
              <Link
                href={link.href}
                className="text-primary break-all underline"
                {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
              >
                {flag.target_type === "org_service" ? "Open organization" : flag.target_id}
              </Link>
            ) : (
              <span className="break-all">{flag.target_id}</span>
            ))}
          <span>· {formatDateTime(flag.created_at)}</span>
          <span className="break-all">· {flag.user_email ?? "anonymous"}</span>
        </div>
        <StatusBadge status={flag.status} />
      </div>
      <p className="leading-relaxed break-words">{flag.message}</p>
      {flag.org_response && (
        <div className="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-sky-950 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-100">
          <p className="font-medium">
            {flag.org_name ?? "The organization"} says: {flag.org_verdict === "fixed" ? "fixed it" : flag.org_verdict === "correct" ? "the information is correct" : "answered"}
          </p>
          <p className="break-words">{flag.org_response}</p>
          <p className="text-[11px] opacity-80">
            {flag.org_responded_by} {flag.org_responded_at && `· ${formatDateTime(flag.org_responded_at)}`}
          </p>
        </div>
      )}
      {flag.events.length > 1 && (
        <details>
          <summary className="text-muted-foreground cursor-pointer text-[11px]">History ({flag.events.length})</summary>
          <ol className="text-muted-foreground mt-1 space-y-0.5 text-[11px]">
            {flag.events.map((e, i) => (
              <li key={i} className="break-words">
                {formatDateTime(e.created_at)} · {EVENT_LABEL[e.action] ?? humanize(e.action)}
                {e.actor && ` by ${e.actor}`}
                {e.note && `: “${e.note}”`}
              </li>
            ))}
          </ol>
        </details>
      )}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <label htmlFor={noteId} className="sr-only">
          {flag.status === "open" ? "Resolution note" : "Reason for reopening"}
        </label>
        <Input
          id={noteId}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={flag.status === "open" ? "Note, shown to the reporter when resolved (optional)" : "Why reopen (optional)"}
        />
        {flag.status === "open" ? (
          <div className="flex gap-2">
            <Button size="sm" loading={isPending} onClick={() => act("resolved")}>
              Resolve
            </Button>
            <Button size="sm" variant="outline" disabled={isPending} onClick={() => act("dismissed")}>
              Dismiss
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground text-[11px]">
              {humanize(flag.status)} by {flag.resolved_by ?? "-"}
              {flag.resolution_note && `: “${flag.resolution_note}”`}
            </span>
            <Button size="xs" variant="ghost" loading={isPending} onClick={() => act("open")}>
              Reopen
            </Button>
          </div>
        )}
      </div>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
    </li>
  );
}

export function FeedbackPage() {
  const [filters, setFilters] = useUrlParams({ status: "open", target_type: "", q: "", org_id: "" });
  const [query, setQuery] = useState(filters.q);
  const q = useDebounced(query.trim(), 300);
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(FEEDBACK_PAGE_SIZE);
  const { payload, isLoading, error, refetch } = useFeedbackFlags(filters, page, size);
  const typeId = useId();

  useEffect(() => {
    if (q !== filters.q) setFilters({ q });
    // Only react to typing; a URL change (Back) must not be undone by the old input value
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  return (
    <AdminPage
      title="Feedback queue"
      description="People flag information they believe is wrong: fees, offices, requirements or agents. Fix the source data, then resolve the report. Organizations can answer reports about their own services, but only staff close them."
    >
      <div role="group" aria-label="Filter by status" className="border-border mb-4 flex flex-wrap gap-1 border-b">
        {TABS.map((t) => (
          <button
            key={t.value}
            aria-pressed={filters.status === t.value}
            type="button"
            onClick={() => setFilters({ status: t.value })}
            className={cn(
              "-mb-px border-b-2 border-transparent px-3 py-2 text-xs",
              filters.status === t.value ? "border-primary font-medium" : "text-muted-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Input
          className="max-w-xs"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search message, id or organization"
          aria-label="Search reports"
        />
        <label htmlFor={typeId} className="sr-only">
          About
        </label>
        <NativeSelect id={typeId} value={filters.target_type} onChange={(e) => setFilters({ target_type: e.target.value })}>
          <option value="">Everything</option>
          {TARGET_TYPES.map((t) => (
            <option key={t} value={t}>
              {humanize(t)}
            </option>
          ))}
        </NativeSelect>
        {filters.org_id && (
          <Button size="sm" variant="outline" onClick={() => setFilters({ org_id: "" })}>
            One organization only ✕
          </Button>
        )}
      </div>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !payload?.flags.length ? (
        <EmptyState title="No reports here" description={filters.status === "open" ? "Nothing waiting for review." : undefined} />
      ) : (
        <ul className="space-y-2">
          {payload.flags.map((f) => (
            <FlagItem key={f.id} flag={f} />
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
    </AdminPage>
  );
}
