"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import {
  DATA_SOURCE_RUNS_PAGE_SIZE,
  useDataSourceRuns,
  useMarkRunFailed,
  useRunDataSource,
} from "@cn/core/api/admin";
import { formatDateTime, formatDuration, humanize, timeAgo } from "@cn/core/lib/format";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { NativeSelect } from "@/modules/shared/native-select";
import { ErrorState, EmptyState, LoadingState } from "@/modules/shared/states";
import { StatsList } from "@/modules/shared/stats-list";
import { StatusBadge } from "@/modules/shared/status-badge";
import type { DataSource, DataSourceRun } from "@cn/core/types/admin";
import { cardId, describeChanges, isStuck, summarizeRun } from "./describe";

const STATUSES = ["success", "failed", "running"] as const;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function RunActions({ run, source }: { run: DataSourceRun; source: DataSource | undefined }) {
  const { runSource } = useRunDataSource();
  const { markFailed } = useMarkRunFailed();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const act = async (fn: () => Promise<unknown>, fallback: string) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(getErrorMessage(e, fallback));
    } finally {
      setBusy(false);
    }
  };

  let button: React.ReactNode = null;
  if (run.status === "failed") {
    const why = !source
      ? "This source was deleted"
      : !source.enabled
        ? "The source is paused; resume it first"
        : source.lastRun?.status === "running"
          ? "A run of this source is already in progress"
          : null;
    button = (
      <Button
        size="xs"
        variant="outline"
        loading={busy}
        disabled={!!why}
        title={why ?? "Start a new run of this source now"}
        onClick={() => source && act(() => runSource(source.id), "Couldn't start the run")}
      >
        Run again
      </Button>
    );
  } else if (isStuck(run)) {
    button = (
      <Button
        size="xs"
        variant="destructive"
        loading={busy}
        title="This run stopped answering. Mark it failed so the source can run again."
        onClick={() => act(() => markFailed(run.id), "Couldn't mark the run as failed")}
      >
        Mark as failed
      </Button>
    );
  }
  return (
    <div className="flex flex-col items-end gap-1">
      {button}
      {error && (
        <p role="alert" className="text-destructive max-w-[12rem] text-right text-[10px]">
          {error}
        </p>
      )}
    </div>
  );
}

function RunRow({ run, source, pathname }: { run: DataSourceRun; source: DataSource | undefined; pathname: string }) {
  const [open, setOpen] = useState(false);
  const panelId = `run-${run.id}`;
  const label = run.source_label ?? source?.label ?? run.source;
  const changes = run.status === "success" ? describeChanges(run.stats) : [];
  return (
    <>
      <tr className={cn("border-border border-t align-top", open && "bg-muted/40")}>
        <td className="py-2 pr-3">
          <button
            type="button"
            className="flex items-start gap-1.5 text-left font-medium"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((o) => !o)}
          >
            <span aria-hidden className={cn("text-muted-foreground inline-block transition-transform", open && "rotate-90")}>
              ▸
            </span>
            <span className="break-words">{label}</span>
          </button>
          <span className="text-muted-foreground block pl-4 text-[11px] sm:hidden" title={formatDateTime(run.started_at)}>
            {timeAgo(run.started_at)} · {formatDuration(run.duration_s)}
          </span>
        </td>
        <td className="py-2 pr-3">
          <StatusBadge status={isStuck(run) ? "stuck" : run.status} tone={isStuck(run) ? "warning" : undefined} />
        </td>
        <td className="hidden py-2 pr-3 whitespace-nowrap sm:table-cell" title={formatDateTime(run.started_at)}>
          {timeAgo(run.started_at)}
        </td>
        <td className="hidden py-2 pr-3 tabular-nums sm:table-cell">{formatDuration(run.duration_s)}</td>
        <td className="text-muted-foreground hidden max-w-[10rem] truncate py-2 pr-3 lg:table-cell" title={run.triggered_by ?? undefined}>
          {run.triggered_by ?? "-"}
        </td>
        <td className={cn("hidden max-w-[18rem] py-2 pr-3 md:table-cell", run.error && "text-destructive")}>
          <span className="line-clamp-2 break-words">{summarizeRun(run)}</span>
        </td>
        <td className="py-2 text-right">
          <RunActions run={run} source={source} />
        </td>
      </tr>
      {open && (
        <tr id={panelId} className="bg-muted/40">
          <td colSpan={7} className="px-3 pb-3 text-[11px] sm:px-5">
            <p className="text-muted-foreground mb-1.5">
              Started {formatDateTime(run.started_at)}
              {run.finished_at && ` · finished ${formatDateTime(run.finished_at)}`} · took {formatDuration(run.duration_s)}
              {run.triggered_by && ` · started by ${run.triggered_by}`}
            </p>
            {run.error ? (
              <pre className="text-destructive max-h-60 overflow-auto text-[10px] break-words whitespace-pre-wrap">{run.error}</pre>
            ) : changes.length ? (
              <>
                <ul className="mb-1.5 list-disc space-y-0.5 pl-4">
                  {changes.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
                <StatsList stats={run.stats} />
              </>
            ) : (
              <p>{summarizeRun(run)}</p>
            )}
            {source && (
              <Link href={`${pathname}#${cardId(source.id)}`} className="text-primary mt-2 inline-block underline">
                Go to the “{source.label}” source
              </Link>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export function RunHistory({ sources, poll }: { sources: DataSource[]; poll: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const source = params.get("source") ?? "";
  const status = (STATUSES as readonly string[]).includes(params.get("status") ?? "") ? params.get("status")! : "";
  const from = DATE_RE.test(params.get("from") ?? "") ? params.get("from")! : "";
  const to = DATE_RE.test(params.get("to") ?? "") ? params.get("to")! : "";
  const badRange = !!from && !!to && from > to;
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(DATA_SOURCE_RUNS_PAGE_SIZE);
  const runs = useDataSourceRuns({ source, status, from: badRange ? "" : from, to: badRange ? "" : to, page, size }, poll);
  const byId = Object.fromEntries(sources.map((s) => [s.id, s]));
  const items = runs.payload?.items ?? [];
  const total = runs.payload?.total ?? 0;
  const filtered = !!(source || status || from || to);

  // A new filter always starts from the first page
  const setFilters = (changes: Partial<Record<"source" | "status" | "from" | "to", string>>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    next.delete("page");
    router.replace(`${pathname}?${next}`, { scroll: false });
  };

  return (
    <section aria-label="Run history">
      <p className="text-muted-foreground mb-3 max-w-3xl text-[11px] leading-relaxed">
        Every run of every source, newest first: who or what started it, how long it took and what it changed. Open a
        row for the full result or error. “Run again” retries a failed run; “Mark as failed” clears a run that stopped
        answering.
      </p>
      <div className="mb-3 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-end">
        <label className="col-span-2 flex flex-col gap-1 text-[11px] sm:col-span-1">
          <span className="text-muted-foreground">Source</span>
          <NativeSelect value={source} onChange={(e) => setFilters({ source: e.target.value })} className="w-full sm:w-56">
            <option value="">All sources</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="col-span-2 flex flex-col gap-1 text-[11px] sm:col-span-1">
          <span className="text-muted-foreground">Result</span>
          <NativeSelect value={status} onChange={(e) => setFilters({ status: e.target.value })} className="w-full sm:w-36">
            <option value="">Any result</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </NativeSelect>
        </label>
        <label className="flex min-w-0 flex-col gap-1 text-[11px]">
          <span className="text-muted-foreground">Started from</span>
          <Input type="date" value={from} max={to || undefined} onChange={(e) => setFilters({ from: e.target.value })} className="sm:w-40" />
        </label>
        <label className="flex min-w-0 flex-col gap-1 text-[11px]">
          <span className="text-muted-foreground">Started up to</span>
          <Input type="date" value={to} min={from || undefined} onChange={(e) => setFilters({ to: e.target.value })} className="sm:w-40" />
        </label>
        {filtered && (
          <Button
            variant="ghost"
            size="sm"
            className="col-span-2 justify-self-start sm:col-span-1"
            onClick={() => setFilters({ source: "", status: "", from: "", to: "" })}
          >
            Clear filters
          </Button>
        )}
      </div>
      {badRange && (
        <p role="alert" className="text-destructive mb-3 text-[11px]">
          The “Started from” date is after the “Started up to” date, so the dates are ignored until you fix them.
        </p>
      )}
      {runs.payload && (
        <p className="text-muted-foreground mb-2 text-[11px]" aria-live="polite">
          {total.toLocaleString("en")} run{total === 1 ? "" : "s"}
          {filtered ? " match these filters" : " in total"}
        </p>
      )}
      {runs.isLoading ? (
        <LoadingState />
      ) : runs.error ? (
        <ErrorState message={getErrorMessage(runs.error)} onRetry={() => runs.refetch()} />
      ) : !items.length ? (
        filtered ? (
          <EmptyState title="No runs match" description="Try another source, result or date range." />
        ) : (
          <EmptyState title="No runs yet" description="Use “Run now” on a source to start one." />
        )
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="py-2 pr-3 font-medium">Source</th>
                <th className="py-2 pr-3 font-medium">Result</th>
                <th className="hidden py-2 pr-3 font-medium sm:table-cell">Started</th>
                <th className="hidden py-2 pr-3 font-medium sm:table-cell" title="How long the run took">
                  Duration
                </th>
                <th className="hidden py-2 pr-3 font-medium lg:table-cell" title="The staff member who pressed Run now, or the automatic schedule (celery or schedule)">
                  Started by
                </th>
                <th className="hidden py-2 pr-3 font-medium md:table-cell">What happened</th>
                <th className="py-2 text-right font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <RunRow key={r.id} run={r} source={byId[r.source]} pathname={pathname} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={page} pageSize={size} total={total} onPage={setPage} onPageSize={setSize} />
    </section>
  );
}
