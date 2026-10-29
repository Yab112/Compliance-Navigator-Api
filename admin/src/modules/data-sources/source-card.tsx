"use client";

import { useState } from "react";
import Link from "next/link";
import { Badge } from "@cn/ui/badge";
import { Button, buttonVariants } from "@cn/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@cn/ui/card";
import {
  useDeleteCustomDataSource,
  useMarkRunFailed,
  usePauseDataSource,
  useRunDataSource,
} from "@cn/core/api/admin";
import { formatDateTime, formatDay, formatDuration, timeAgo } from "@cn/core/lib/format";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { StatsList } from "@/modules/shared/stats-list";
import { StatusBadge } from "@/modules/shared/status-badge";
import type { DataSource, DataSourceHealth } from "@cn/core/types/admin";
import {
  DESTINATIONS,
  KIND_LABEL,
  STUCK_AFTER_MINUTES,
  cardId,
  describeChanges,
  firstLine,
  isFailing,
  isStuck,
  percent,
  scheduleText,
} from "./describe";

/** Runs an async action and keeps its busy and error state, for small buttons. */
function useAction() {
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
  return { busy, error, act };
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

function Metric({ label, help, children }: { label: string; help: string; children: React.ReactNode }) {
  return (
    <div title={help}>
      <dt className="text-muted-foreground decoration-muted-foreground/50 w-fit cursor-help underline decoration-dotted underline-offset-2">
        {label}
      </dt>
      <dd className="text-sm font-semibold tabular-nums">{children}</dd>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-foreground font-medium">{label}</dt>
      <dd className="text-muted-foreground mt-0.5 leading-snug">{children}</dd>
    </div>
  );
}

function LastChange({ source }: { source: DataSource }) {
  const run = source.lastRun;
  if (!run) return <>Nothing yet: this source has never run.</>;
  if (run.status === "running") {
    return isStuck(run) ? (
      <span className="text-amber-700 dark:text-amber-400">
        A run started {timeAgo(run.started_at)} and has not answered for over {STUCK_AFTER_MINUTES} minutes. It has
        probably stopped; use “Mark as failed” to clear it.
      </span>
    ) : (
      <>A run is in progress (started {timeAgo(run.started_at)}). This page updates by itself.</>
    );
  }
  if (run.status === "failed") {
    return (
      <span className="text-destructive break-words" title={run.error ?? undefined}>
        The last run ({timeAgo(run.started_at)}) failed and changed nothing: {firstLine(run.error ?? "no reason recorded")}
      </span>
    );
  }
  const lines = describeChanges(run.stats);
  if (!lines.length) return <>The last run finished {timeAgo(run.finished_at)} with nothing to report.</>;
  return (
    <ul className="list-disc space-y-0.5 pl-4">
      {lines.map((l) => (
        <li key={l}>{l}</li>
      ))}
    </ul>
  );
}

export function SourceCard({
  source,
  runsHref,
  onEdit,
}: {
  source: DataSource;
  runsHref: string;
  onEdit?: () => void;
}) {
  const run = source.lastRun;
  const h = source.health;
  const running = run?.status === "running";
  const stuck = isStuck(run);
  const failing = isFailing(h);
  const schedule = scheduleText(source);
  const custom = source.custom;

  const { runSource } = useRunDataSource();
  const { setPaused } = usePauseDataSource();
  const { markFailed } = useMarkRunFailed();
  const { remove } = useDeleteCustomDataSource();
  const action = useAction();
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <Card
      id={cardId(source.id)}
      size="sm"
      className={cn("h-full scroll-mt-20", failing && source.enabled && "ring-destructive/40", !source.enabled && "opacity-90")}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="break-words">{source.label}</CardTitle>
            <div className="mt-1 flex flex-wrap gap-1">
              <Badge variant="outline">{KIND_LABEL[source.kind] ?? source.kind}</Badge>
              <Badge variant="outline" className="text-muted-foreground">
                {source.builtIn ? "Built in" : "Added by staff"}
              </Badge>
            </div>
          </div>
          {!source.enabled ? (
            <StatusBadge status="paused" tone="warning" />
          ) : (
            <StatusBadge
              status={stuck ? "stuck" : (run?.status ?? "never run")}
              tone={stuck ? "warning" : run ? undefined : "neutral"}
            />
          )}
        </div>
        {!source.enabled && (
          <p className="mt-2 bg-amber-500/10 px-2 py-1.5 text-[11px] text-amber-800 dark:text-amber-300">
            Paused{source.pausedBy && ` by ${source.pausedBy}`}
            {source.pausedAt && ` ${timeAgo(source.pausedAt)}`}. It won&apos;t run, by hand or on its schedule, until
            someone resumes it.
          </p>
        )}
        {source.description && <CardDescription className="sr-only">{source.description}</CardDescription>}
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3 text-[11px]">
        <dl className="space-y-2">
          <Fact label="What it does">{source.description || "No description given."}</Fact>
          <Fact label="Where the data goes">
            <ul className="space-y-0.5">
              {source.destinations.map((d) => (
                <li key={d}>
                  <span className="text-foreground">{DESTINATIONS[d]?.label ?? d}</span>
                  {DESTINATIONS[d] && `: ${DESTINATIONS[d].help}`}
                </li>
              ))}
            </ul>
          </Fact>
          <Fact label="When it runs">
            {schedule.text}
            {schedule.note && <span className="block text-[10px] opacity-80">{schedule.note}</span>}
          </Fact>
          <Fact label="What the last run changed">
            <LastChange source={source} />
          </Fact>
        </dl>

        <dl className="border-border grid grid-cols-3 gap-2 border-t pt-2">
          <Metric
            label={`Success (${h.windowDays}d)`}
            help={`Share of runs in the last ${h.windowDays} days that finished without an error. Runs still in progress are not counted.`}
          >
            {percent(h.successRate)}
          </Metric>
          <Metric
            label="Runs"
            help={`How many times it ran in the last ${h.windowDays} days, by hand or on schedule.`}
          >
            {h.runs}
            {h.failures > 0 && <span className="text-destructive text-[11px] font-normal"> ({h.failures} failed)</span>}
          </Metric>
          <Metric
            label="Avg time"
            help={`Average time a finished run took over the last ${h.windowDays} days. The last run took ${formatDuration(h.lastDurationS)}.`}
          >
            {formatDuration(h.avgDurationS)}
          </Metric>
        </dl>
        <div>
          <RunSparkline health={h} />
          <p className="text-muted-foreground mt-0.5 flex justify-between text-[10px]">
            <span>{h.windowDays} days ago</span>
            <span>Today</span>
          </p>
        </div>
        <p className="text-muted-foreground">
          Last run {run ? `${timeAgo(run.started_at)} · took ${formatDuration(run.duration_s)}` : "never"}
          {run?.triggered_by && ` · started by ${run.triggered_by}`}
          {h.lastSuccessAt && ` · last success ${timeAgo(h.lastSuccessAt)}`}
        </p>

        <details className="group mt-auto">
          <summary className="text-primary cursor-pointer select-none">More details</summary>
          <div className="mt-2 space-y-2">
            <p className="text-muted-foreground">
              All time: {source.successes} successful · {source.failures} failed
            </p>
            {custom && (
              <dl className="text-muted-foreground grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
                <dt>Issued by</dt>
                <dd className="text-foreground break-words">{custom.issuing_body || "-"}</dd>
                <dt>Language</dt>
                <dd className="text-foreground">{custom.language === "am" ? "Amharic" : "English"}</dd>
                <dt>Topics</dt>
                <dd className="text-foreground break-words">{custom.tags.length ? custom.tags.join(", ") : "-"}</dd>
                <dt>In knowledge base</dt>
                <dd className="text-foreground">{(custom.passages ?? 0).toLocaleString("en")} passages</dd>
                {custom.kind === "pasted_text" && (
                  <>
                    <dt>Text length</dt>
                    <dd className="text-foreground">{custom.text_length.toLocaleString("en")} characters</dd>
                  </>
                )}
                <dt>Added</dt>
                <dd className="text-foreground break-words">
                  {formatDateTime(custom.created_at)}
                  {custom.created_by && ` by ${custom.created_by}`}
                </dd>
                {custom.updated_at !== custom.created_at && (
                  <>
                    <dt>Last edited</dt>
                    <dd className="text-foreground break-words">
                      {formatDateTime(custom.updated_at)}
                      {custom.updated_by && ` by ${custom.updated_by}`}
                    </dd>
                  </>
                )}
              </dl>
            )}
            {run?.status === "success" && (
              <div>
                <p className="text-muted-foreground mb-0.5">Raw numbers from the last run</p>
                <StatsList stats={run.stats} />
              </div>
            )}
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

      <CardFooter className="flex-col items-stretch gap-2">
        {confirmDelete ? (
          <div role="group" aria-label="Confirm delete" className="bg-destructive/5 space-y-2 p-2 text-[11px]">
            <p>
              Delete “{source.label}”? Its {(custom?.passages ?? 0).toLocaleString("en")} passages are removed from the
              AI knowledge base, so the assistant stops quoting it. Its run history is kept.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="destructive"
                loading={action.busy}
                onClick={() => custom && action.act(() => remove(custom.id), "Couldn't delete the source")}
              >
                Yes, delete
              </Button>
              <Button size="sm" variant="outline" disabled={action.busy} onClick={() => setConfirmDelete(false)} autoFocus>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-end gap-1.5">
            <Link href={runsHref} scroll={false} className={buttonVariants({ size: "sm", variant: "ghost" })}>
              View runs
            </Link>
            {custom && (
              <>
                <Button size="sm" variant="ghost" onClick={onEdit}>
                  Edit
                </Button>
                <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setConfirmDelete(true)}>
                  Delete
                </Button>
              </>
            )}
            <Button
              size="sm"
              variant="outline"
              loading={action.busy}
              title={
                source.enabled
                  ? "Stop this source from running, by hand or on its schedule"
                  : "Let this source run again, by hand and on its schedule"
              }
              onClick={() =>
                action.act(() => setPaused(source.id, source.enabled), source.enabled ? "Couldn't pause" : "Couldn't resume")
              }
            >
              {source.enabled ? "Pause" : "Resume"}
            </Button>
            {stuck && run ? (
              <Button
                size="sm"
                variant="destructive"
                loading={action.busy}
                title={`The run started ${timeAgo(run.started_at)} and stopped answering. Mark it failed so the source can run again.`}
                onClick={() => action.act(() => markFailed(run.id), "Couldn't mark the run as failed")}
              >
                Mark as failed
              </Button>
            ) : (
              <Button
                size="sm"
                loading={action.busy}
                disabled={running || !source.enabled}
                title={!source.enabled ? "Resume the source first" : running ? "A run is already in progress" : undefined}
                onClick={() => action.act(() => runSource(source.id), "Couldn't start the run")}
              >
                {running ? "Running…" : "Run now"}
              </Button>
            )}
          </div>
        )}
        {action.error && (
          <p role="alert" className="text-destructive text-right text-[11px]">
            {action.error}
          </p>
        )}
      </CardFooter>
    </Card>
  );
}
