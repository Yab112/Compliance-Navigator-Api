"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pager, useUrlPage } from "@/components/ui/pager";
import { FEEDBACK_PAGE_SIZE, useFeedbackFlags, useResolveFlag } from "@/api/admin";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { AdminPage } from "@/modules/admin/components/admin-page";
import { formatDateTime, humanize } from "@/modules/admin/shared/format";
import { EmptyState, ErrorState, LoadingState } from "@/modules/admin/shared/states";
import { StatusBadge } from "@/modules/admin/shared/status-badge";
import type { FeedbackFlag } from "@/types/admin";

const TABS = ["open", "resolved", "dismissed"] as const;

function targetLink(flag: FeedbackFlag) {
  if (!flag.target_id) return null;
  if (flag.target_type === "document" || flag.target_type === "roadmap_step") return "/admin/graph";
  if (flag.target_type === "gov_service") return `/services/${flag.target_id}`;
  if (flag.target_type === "agent") return `/admin/marketplace/${flag.target_id}`;
  return null;
}

function FlagItem({ flag }: { flag: FeedbackFlag }) {
  const { resolveFlag, isPending } = useResolveFlag();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const href = targetLink(flag);

  const act = async (status: string) => {
    setError(null);
    try {
      await resolveFlag(flag.id, status, note || undefined);
    } catch (e) {
      setError(getErrorMessage(e, "Couldn't update the flag"));
    }
  };

  return (
    <li className="border-border space-y-2 border p-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 text-[11px]">
          <span className="text-foreground font-medium">{humanize(flag.target_type)}</span>
          {flag.target_id &&
            (href ? (
              <Link href={href} className="text-primary underline">
                {flag.target_id}
              </Link>
            ) : (
              <span>{flag.target_id}</span>
            ))}
          <span>· {formatDateTime(flag.created_at)}</span>
          <span>· {flag.user_email ?? "anonymous"}</span>
        </div>
        <StatusBadge status={flag.status} />
      </div>
      <p className="leading-relaxed">{flag.message}</p>
      {flag.status === "open" ? (
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Resolution note (optional)" aria-label="Resolution note" />
          <div className="flex gap-2">
            <Button size="sm" loading={isPending} onClick={() => act("resolved")}>
              Resolve
            </Button>
            <Button size="sm" variant="outline" disabled={isPending} onClick={() => act("dismissed")}>
              Dismiss
            </Button>
          </div>
        </div>
      ) : (
        <div className="text-muted-foreground flex flex-wrap items-center justify-between gap-2 text-[11px]">
          <span>
            {humanize(flag.status)} by {flag.resolved_by ?? "-"} {flag.resolved_at && `· ${formatDateTime(flag.resolved_at)}`}
            {flag.resolution_note && `: “${flag.resolution_note}”`}
          </span>
          <Button size="xs" variant="ghost" loading={isPending} onClick={() => act("open")}>
            Reopen
          </Button>
        </div>
      )}
      {error && <p className="text-destructive">{error}</p>}
    </li>
  );
}

export function FeedbackPage() {
  const [tab, setTabState] = useState<(typeof TABS)[number]>("open");
  const [page, setPage] = useUrlPage();
  const setTab = (t: (typeof TABS)[number]) => {
    setTabState(t);
    if (page) setPage(0);
  };
  const { payload, isLoading, error, refetch } = useFeedbackFlags(tab, page);

  return (
    <AdminPage
      title="Feedback queue"
      description="Citizens flag information they believe is wrong: fees, offices, requirements or agents. Fix the source data, then resolve the flag."
    >
      <div role="tablist" className="border-border mb-4 flex gap-1 border-b">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "-mb-px border-b-2 border-transparent px-3 py-2 text-xs capitalize",
              tab === t ? "border-primary font-medium" : "text-muted-foreground",
            )}
          >
            {t}
          </button>
        ))}
      </div>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !payload?.flags.length ? (
        <EmptyState title={`No ${tab} flags`} description={tab === "open" ? "Nothing waiting for review." : undefined} />
      ) : (
        <ul className="space-y-2">
          {payload.flags.map((f) => (
            <FlagItem key={f.id} flag={f} />
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={FEEDBACK_PAGE_SIZE} total={payload?.total ?? 0} onPage={setPage} />
    </AdminPage>
  );
}
