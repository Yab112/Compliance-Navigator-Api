"use client";

import Link from "next/link";
import { useEffect } from "react";
import { SAVED_PATHS_PAGE_SIZE, useRemovePath, useSavedPaths } from "@/api/roadmap/saved";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@/components/ui/button";
import { Pager, useUrlPage } from "@/components/ui/pager";
import { formatDateTime } from "@/modules/admin/shared/format";
import { EmptyState, ErrorState, LoadingState } from "@/modules/guday/components/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";

/** /account/paths: every path saved to this account, with progress. */
export function SavedPaths() {
  const gate = useAuthGate();
  const [page, setPage] = useUrlPage();
  const { data, isLoading, isError, error, refetch } = useSavedPaths(page);
  const remove = useRemovePath();
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  // Removing the last path on a page: step back to the last page that still has paths
  useEffect(() => {
    if (data && !data.items.length && page > 0)
      setPage(Math.max(0, Math.ceil(data.total / SAVED_PATHS_PAGE_SIZE) - 1));
  }, [data, page, setPage]);

  return (
    <PageShell
      title="My saved paths · የተቀመጡ መንገዶቼ"
      description="Paths you saved, with the steps you've already done. They follow you to any device you sign in on."
      maxWidth="lg"
    >
      <div className="mb-4 flex flex-wrap gap-2">
        <Link
          href="/roadmap/new"
          className="bg-primary text-primary-foreground rounded-md px-3 py-1.5 text-sm font-semibold"
        >
          Find a new path
        </Link>
      </div>

      {gate === "loading" || isLoading ? (
        <LoadingState label="Loading your paths…" />
      ) : isError ? (
        <ErrorState
          message={error?.message ?? "Could not load your paths"}
          onRetry={() => refetch()}
        />
      ) : !items.length ? (
        <EmptyState title="No saved paths yet">
          <p>Find a path, then press &quot;Save path&quot; to keep it here.</p>
        </EmptyState>
      ) : (
        <>
          <p className="text-muted-foreground mb-2 text-xs">
            {total} saved path{total === 1 ? "" : "s"}
          </p>
          <ul className="grid gap-3">
            {items.map((p) => {
              const pct = p.steps
                ? Math.round((Math.min(p.completed, p.steps) / p.steps) * 100)
                : 0;
              return (
                <li
                  key={p.id}
                  className="border-border bg-card flex flex-wrap items-center gap-4 rounded-md border p-4"
                >
                  <div className="min-w-0 flex-1">
                    <Link
                      href={`/roadmap/${p.id}`}
                      className="text-gov-ink font-semibold hover:underline"
                    >
                      Path to: {p.goalLabel}
                    </Link>
                    <p className="text-muted-foreground mt-0.5 text-xs">
                      {[
                        p.subCityLabel,
                        `${Math.min(p.completed, p.steps)} of ${p.steps} steps done`,
                        `updated ${formatDateTime(p.updatedAt)}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                    <div
                      className="bg-secondary mt-2 h-1.5 max-w-sm overflow-hidden rounded-full"
                      aria-label={`${pct}% done`}
                    >
                      <div className="bg-primary h-full" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Link href={`/roadmap/${p.id}`}>
                      <Button size="sm">Open</Button>
                    </Link>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(p.id)}
                    >
                      Remove
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
          <Pager page={page} pageSize={SAVED_PATHS_PAGE_SIZE} total={total} onPage={setPage} />
        </>
      )}
    </PageShell>
  );
}
