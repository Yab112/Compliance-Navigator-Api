"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { useDataSourceRuns, useDataSources, useRunDataSource } from "@/api/admin";
import { AdminPage } from "@/modules/admin/components/admin-page";
import { formatDateTime, formatDuration, timeAgo } from "@/modules/admin/shared/format";
import { NativeSelect } from "@/modules/admin/shared/native-select";
import { ErrorState, EmptyState, LoadingState } from "@/modules/admin/shared/states";
import { StatsList } from "@/modules/admin/shared/stats-list";
import { StatusBadge } from "@/modules/admin/shared/status-badge";
import { getErrorMessage } from "@/lib/errors";
import type { DataSource, DataSourceRun } from "@/types/admin";

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

function SourceCard({ source }: { source: DataSource }) {
  const run = source.lastRun;
  const running = run?.status === "running";
  return (
    <Card size="sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle>{source.label}</CardTitle>
            <Badge variant="outline" className="mt-1 capitalize">
              {source.kind}
            </Badge>
          </div>
          <StatusBadge status={run?.status ?? "never run"} tone={run ? undefined : "neutral"} />
        </div>
        <CardDescription>{source.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-[11px]">
        <p className="text-muted-foreground">
          Last run {run ? `${timeAgo(run.started_at)} · ${formatDuration(run.duration_s)}` : "never"}
          {run?.triggered_by && ` · by ${run.triggered_by}`}
        </p>
        {run && run.status === "success" && <StatsList stats={run.stats} />}
        {run?.status === "failed" && run.error && (
          <p className="text-destructive line-clamp-3 break-words">{run.error}</p>
        )}
        <p className="text-muted-foreground">
          {source.successes} successful · {source.failures} failed
          {source.lastSuccessAt && ` · last success ${timeAgo(source.lastSuccessAt)}`}
        </p>
        {source.url && (
          <a href={source.url} target="_blank" rel="noreferrer" className="text-primary break-all underline">
            {source.url}
          </a>
        )}
      </CardContent>
      <CardFooter className="justify-end">
        <RunButton source={source} disabled={running} />
      </CardFooter>
    </Card>
  );
}

function RunRow({ run, label }: { run: DataSourceRun; label: string }) {
  const [open, setOpen] = useState(false);
  return (
    <tr className="border-border border-t align-top">
      <td className="py-2 pr-3 font-medium">{label}</td>
      <td className="py-2 pr-3"><StatusBadge status={run.status} /></td>
      <td className="py-2 pr-3 whitespace-nowrap">{formatDateTime(run.started_at)}</td>
      <td className="py-2 pr-3 tabular-nums">{formatDuration(run.duration_s)}</td>
      <td className="text-muted-foreground py-2 pr-3">{run.triggered_by ?? "-"}</td>
      <td className="py-2">
        {run.error ? (
          <button type="button" className="text-destructive text-left underline-offset-2 hover:underline" onClick={() => setOpen((o) => !o)}>
            {open ? run.error : `${run.error.slice(0, 80)}${run.error.length > 80 ? "… (show)" : ""}`}
          </button>
        ) : (
          <StatsList stats={run.stats} />
        )}
      </td>
    </tr>
  );
}

export function DataSourcesPage() {
  const [filter, setFilter] = useState<string>("");
  // Poll while anything is running; the first fetch decides
  const [poll, setPoll] = useState(false);
  const sources = useDataSources(poll);
  const runs = useDataSourceRuns(filter || null, poll);

  const list = sources.payload?.sources ?? [];
  const anyRunning = list.some((s) => s.lastRun?.status === "running");
  if (anyRunning !== poll) setPoll(anyRunning);
  const labels = Object.fromEntries(list.map((s) => [s.id, s.label]));

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
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {list.map((s) => (
            <SourceCard key={s.id} source={s} />
          ))}
        </div>
      )}

      <section className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Run history</h2>
          <label className="flex items-center gap-2 text-xs">
            Source
            <NativeSelect value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">All sources</option>
              {list.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </NativeSelect>
          </label>
        </div>
        {runs.isLoading ? (
          <LoadingState />
        ) : runs.error ? (
          <ErrorState message={getErrorMessage(runs.error)} onRetry={() => runs.refetch()} />
        ) : !runs.payload?.runs.length ? (
          <EmptyState title="No runs yet" description="Use “Run now” on a source to start one." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-xs">
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
                {runs.payload.runs.map((r) => (
                  <RunRow key={r.id} run={r} label={labels[r.source] ?? r.source} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AdminPage>
  );
}
