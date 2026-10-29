"use client";

import { useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Badge } from "@cn/ui/badge";
import { Button } from "@cn/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@cn/ui/card";
import { Pager, useUrlPage } from "@cn/ui/pager";
import {
  DATA_SOURCE_RUNS_PAGE_SIZE,
  useDataSourceRuns,
  useDataSources,
  useRunDataSource,
} from "@cn/core/api/admin";
import { AdminPage } from "@/modules/components/admin-page";
import { formatDateTime, formatDay, formatDuration, humanize, timeAgo } from "@cn/core/lib/format";
import { cn } from "@cn/core/lib/utils";
import { NativeSelect } from "@/modules/shared/native-select";
import { ErrorState, EmptyState, LoadingState } from "@/modules/shared/states";
import { StatTile } from "@/modules/shared/stat-tile";
import { StatsList } from "@/modules/shared/stats-list";
import { StatusBadge } from "@/modules/shared/status-badge";
import { getErrorMessage } from "@cn/core/lib/errors";
import type { DataSource, DataSourceHealth, DataSourceRun } from "@cn/core/types/admin";

const STATUSES = ["success", "failed", "running"] as const;

const percent = (rate: number | null) => (rate == null ? "-" : `${Math.round(rate * 100)}%`);
const firstLine = (text: string) => text.split("\n").find((l) => l.trim()) ?? text;

/** Failing when the most recent finished run failed. */
function isFailing(h: DataSourceHealth) {
  return !!h.lastFailureAt && (!h.lastSuccessAt || h.lastFailureAt > h.lastSuccessAt);
}

/** One line for a run: graph totals when present, otherwise the first few numeric stats. */
function summarize(run: DataSourceRun): string {
  if (run.status === "running") return "In progress";
  if (run.error) return firstLine(run.error);
  const stats = run.stats ?? {};
  const n = (v: unknown) => (v as number).toLocaleString("en");
  if (typeof stats.totalNodes === "number") {
    return `${n(stats.totalNodes)} nodes, ${n(stats.totalRelationships ?? 0)} relationships`;
  }
  const parts = Object.entries(stats)
    .filter(([, v]) => typeof v === "number")
    .slice(0, 3)
    .map(([k, v]) => `${n(v)} ${humanize(k).toLowerCase()}`);
  return parts.join(", ") || "No stats recorded";
}

function RunButton({ source, disabled }: { source: DataSource; disabled: boolean }) {
  const { runSource } = useRunDataSource();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        size="sm"
        loading={busy}
        disabled={disabled}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await runSource(source.id);
          } catch (e) {
            setError(getErrorMessage(e, "Couldn't start the run"));
          } finally {
            setBusy(false);
          }
        }}
      >
        {disabled ? "Running…" : "Run now"}
      </Button>
      {error && <p className="text-destructive text-[11px]">{error}</p>}
    </div>
  );
}

/** 30 stacked day bars: green successes under red failures, a faint stub for days without runs. */
function RunSparkline({ health }: { health: DataSourceHealth }) {
  const days = health.daily;
  const max = Math.max(1, ...days.map((d) => d.success + d.failed));
  const W = 4;
  const H = 24;
  return (
    <svg
      viewBox={`0 0 ${days.length * W} ${H}`}
      preserveAspectRatio="none"
      className="h-6 w-full"
      role="img"
      aria-label={`Last ${health.windowDays} days: ${health.successes} successful, ${health.failures} failed runs`}
    >
      {days.map((d, i) => {
        const total = d.success + d.failed;
        const x = i * W + 0.5;
        if (!total) return <rect key={d.day} x={x} y={H - 1} width={W - 1} height={1} className="fill-muted-foreground/25" />;
        const failH = (d.failed / max) * H;
        const okH = (d.success / max) * H;
        return (
          <g key={d.day}>
            <title>{`${formatDay(d.day)}: ${d.success} successful, ${d.failed} failed`}</title>
            {okH > 0 && <rect x={x} y={H - okH} width={W - 1} height={okH} className="fill-emerald-500" />}
            {failH > 0 && <rect x={x} y={H - okH - failH} width={W - 1} height={failH} className="fill-destructive" />}
          </g>
        );
      })}
    </svg>
  );
}

function SourceCard({ source }: { source: DataSource }) {
  const run = source.lastRun;
  const h = source.health;
  const running = run?.status === "running";
  const failing = isFailing(h);
  const lastDetails = run && run.status !== "running" ? run : null;
  return (
    <Card size="sm" className={cn("h-full", failing && "ring-destructive/40")}>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="truncate" title={source.label}>
              {source.label}
            </CardTitle>
            <Badge variant="outline" className="mt-1 capitalize">
              {source.kind}
            </Badge>
          </div>
          <StatusBadge status={run?.status ?? "never run"} tone={run ? undefined : "neutral"} />
        </div>
        <CardDescription className="line-clamp-2" title={source.description}>
          {source.description}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-2 text-[11px]">
        <p className="text-muted-foreground truncate">
          Last run {run ? `${timeAgo(run.started_at)} · ${formatDuration(run.duration_s)}` : "never"}
          {run?.triggered_by && ` · by ${run.triggered_by}`}
        </p>
        <dl className="grid grid-cols-3 gap-2">
          <div>
            <dt className="text-muted-foreground">Success ({h.windowDays}d)</dt>
            <dd className="text-sm font-semibold tabular-nums">{percent(h.successRate)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Runs</dt>
            <dd className="text-sm font-semibold tabular-nums">
              {h.runs}
              {h.failures > 0 && <span className="text-destructive text-[11px] font-normal"> ({h.failures} failed)</span>}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Avg time</dt>
            <dd className="text-sm font-semibold tabular-nums">{formatDuration(h.avgDurationS)}</dd>
          </div>
        </dl>
        <RunSparkline health={h} />
        {failing && h.lastFailureError ? (
          <p className="text-destructive line-clamp-2 break-words" title={h.lastFailureError}>
            Failed {timeAgo(h.lastFailureAt)}: {firstLine(h.lastFailureError)}
          </p>
        ) : (
          <p className="text-muted-foreground">Last success {timeAgo(h.lastSuccessAt)}</p>
        )}
        <details className="group mt-auto">
          <summary className="text-primary cursor-pointer select-none">Details</summary>
          <div className="mt-2 space-y-2">
            <p className="text-muted-foreground">{source.description}</p>
            <p className="text-muted-foreground">
              All time: {source.successes} successful · {source.failures} failed · last run took{" "}
              {formatDuration(h.lastDurationS)}
            </p>
            {lastDetails?.status === "success" && <StatsList stats={lastDetails.stats} />}
            {h.lastFailureError && (
              <div>
                <p className="text-muted-foreground">Last failure {formatDateTime(h.lastFailureAt)}</p>
                <pre className="text-destructive mt-1 max-h-40 overflow-auto text-[10px] break-words whitespace-pre-wrap">
                  {h.lastFailureError}
                </pre>
              </div>
            )}
            {source.url && (
              <a href={source.url} target="_blank" rel="noreferrer" className="text-primary block break-all underline">
                {source.url}
              </a>
            )}
          </div>
        </details>
      </CardContent>
      <CardFooter className="justify-end">
        <RunButton source={source} disabled={running} />
      </CardFooter>
    </Card>
  );
}

function SummaryStrip({ sources }: { sources: DataSource[] }) {
  const ran = sources.filter((s) => s.lastRun);
  const failing = ran.filter((s) => isFailing(s.health));
  const runs = sources.reduce((n, s) => n + s.health.runs, 0);
  const ok = sources.reduce((n, s) => n + s.health.successes, 0);
  const bad = sources.reduce((n, s) => n + s.health.failures, 0);
  const lastFailure = sources
    .filter((s) => s.health.lastFailureAt)
    .sort((a, b) => (b.health.lastFailureAt ?? "").localeCompare(a.health.lastFailureAt ?? ""))[0];
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      <StatTile label="Healthy" value={`${ran.length - failing.length} of ${sources.length}`} hint="Last finished run succeeded" />
      <StatTile
        label="Failing"
        value={failing.length}
        hint={failing.length ? failing.map((s) => s.label).join(", ") : "Nothing failing"}
        tone={failing.length ? "attention" : "default"}
      />
      <StatTile label="Never run" value={sources.length - ran.length} />
      <StatTile label="Runs (30 days)" value={runs} hint={`${ok} successful · ${bad} failed`} />
      <StatTile label="Success rate (30 days)" value={percent(ok + bad ? ok / (ok + bad) : null)} />
      <StatTile
        label="Last failure"
        value={lastFailure ? timeAgo(lastFailure.health.lastFailureAt) : "None"}
        hint={lastFailure?.label}
      />
    </div>
  );
}

function RunRow({ run, label }: { run: DataSourceRun; label: string }) {
  const [open, setOpen] = useState(false);
  const panelId = `run-${run.id}`;
  return (
    <>
      <tr className={cn("border-border border-t", open && "bg-muted/40")}>
        <td className="py-2 pr-3">
          <button
            type="button"
            className="flex items-center gap-1.5 text-left font-medium"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((o) => !o)}
          >
            <span aria-hidden className={cn("text-muted-foreground inline-block transition-transform", open && "rotate-90")}>
              ▸
            </span>
            {label}
          </button>
        </td>
        <td className="py-2 pr-3"><StatusBadge status={run.status} /></td>
        <td className="py-2 pr-3 whitespace-nowrap" title={formatDateTime(run.started_at)}>
          {timeAgo(run.started_at)}
        </td>
        <td className="py-2 pr-3 tabular-nums">{formatDuration(run.duration_s)}</td>
        <td className="text-muted-foreground max-w-[10rem] truncate py-2 pr-3">{run.triggered_by ?? "-"}</td>
        <td className={cn("max-w-[18rem] truncate py-2", run.error && "text-destructive")}>{summarize(run)}</td>
      </tr>
      {open && (
        <tr id={panelId} className="bg-muted/40">
          <td colSpan={6} className="px-5 pb-3 text-[11px]">
            <p className="text-muted-foreground mb-1.5">
              Started {formatDateTime(run.started_at)}
              {run.finished_at && ` · finished ${formatDateTime(run.finished_at)}`}
            </p>
            {run.error ? (
              <pre className="text-destructive max-h-60 overflow-auto text-[10px] break-words whitespace-pre-wrap">{run.error}</pre>
            ) : (
              <StatsList stats={run.stats} />
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function RunHistory({ sources, poll }: { sources: DataSource[]; poll: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const source = params.get("source") ?? "";
  const status = (STATUSES as readonly string[]).includes(params.get("status") ?? "") ? params.get("status")! : "";
  const [page, setPage] = useUrlPage();
  const runs = useDataSourceRuns({ source, status, page }, poll);
  const labels = Object.fromEntries(sources.map((s) => [s.id, s.label]));
  const items = runs.payload?.items ?? [];
  const total = runs.payload?.total ?? 0;

  // A new filter always starts from the first page
  const setFilter = (key: "source" | "status", value: string) => {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  return (
    <section className="mt-8">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">
          Run history
          {runs.payload && <span className="text-muted-foreground font-normal tabular-nums"> ({total.toLocaleString("en")})</span>}
        </h2>
        <div className="flex flex-wrap gap-2">
          <NativeSelect aria-label="Filter by source" value={source} onChange={(e) => setFilter("source", e.target.value)}>
            <option value="">All sources</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect aria-label="Filter by status" value={status} onChange={(e) => setFilter("status", e.target.value)}>
            <option value="">Any status</option>
            {STATUSES.map((s) => (
              <option key={s} value={s} className="capitalize">
                {humanize(s)}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>
      {runs.isLoading ? (
        <LoadingState />
      ) : runs.error ? (
        <ErrorState message={getErrorMessage(runs.error)} onRetry={() => runs.refetch()} />
      ) : !items.length ? (
        source || status ? (
          <EmptyState title="No runs match" description="Try another source or status." />
        ) : (
          <EmptyState title="No runs yet" description="Use “Run now” on a source to start one." />
        )
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="py-2 pr-3 font-medium">Source</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Started</th>
                <th className="py-2 pr-3 font-medium">Duration</th>
                <th className="py-2 pr-3 font-medium">Triggered by</th>
                <th className="py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <RunRow key={r.id} run={r} label={labels[r.source] ?? r.source} />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={page} pageSize={DATA_SOURCE_RUNS_PAGE_SIZE} total={total} onPage={setPage} />
    </section>
  );
}

export function DataSourcesPage() {
  // Poll while anything is running; the first fetch decides
  const [poll, setPoll] = useState(false);
  const sources = useDataSources(poll);

  const list = sources.payload?.sources ?? [];
  const anyRunning = list.some((s) => s.lastRun?.status === "running");
  if (anyRunning !== poll) setPoll(anyRunning);

  return (
    <AdminPage
      title="Data sources"
      description="Pipelines that keep the platform's knowledge current: the MESOB catalog scraper, Neo4j graph sync, AI knowledge-base embedding and maintenance checks. Runs execute in the background and are logged below."
    >
      {sources.isLoading ? (
        <LoadingState />
      ) : sources.error ? (
        <ErrorState message={getErrorMessage(sources.error)} onRetry={() => sources.refetch()} />
      ) : (
        <>
          <SummaryStrip sources={list} />
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {list.map((s) => (
              <SourceCard key={s.id} source={s} />
            ))}
          </div>
        </>
      )}
      <RunHistory sources={list} poll={poll} />
    </AdminPage>
  );
}
