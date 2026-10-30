"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Button } from "@cn/ui/button";
import { useDataSourceRunTotal, useDataSources } from "@cn/core/api/admin";
import { AdminPage } from "@/modules/components/admin-page";
import { timeAgo } from "@cn/core/lib/format";
import { cn } from "@cn/core/lib/utils";
import { ErrorState, LoadingState } from "@/modules/shared/states";
import { StatTile } from "@/modules/shared/stat-tile";
import { StatusBadge } from "@/modules/shared/status-badge";
import { getErrorMessage } from "@cn/core/lib/errors";
import type { DataSource } from "@cn/core/types/admin";
import { DESTINATIONS, STUCK_AFTER_MINUTES, cardId, isFailing, percent } from "./describe";
import { RunHistory } from "./run-history";
import { SourceCard } from "./source-card";
import { SourceForm } from "./source-form";

type Tab = "sources" | "runs";

// ---------------------------------------------------------------- "How this works", remembered per viewer

const EXPLAINER_KEY = "cn.admin.data-sources.explainer-hidden";
const EXPLAINER_EVENT = "cn-explainer-change";

function readExplainerHidden() {
  try {
    return window.localStorage.getItem(EXPLAINER_KEY) === "1";
  } catch {
    return false;
  }
}

function subscribeExplainer(cb: () => void) {
  window.addEventListener("storage", cb);
  window.addEventListener(EXPLAINER_EVENT, cb);
  return () => {
    window.removeEventListener("storage", cb);
    window.removeEventListener(EXPLAINER_EVENT, cb);
  };
}

function setExplainerHidden(hidden: boolean) {
  try {
    if (hidden) window.localStorage.setItem(EXPLAINER_KEY, "1");
    else window.localStorage.removeItem(EXPLAINER_KEY);
  } catch {
    // Storage blocked (private window): the choice just isn't remembered
  }
  window.dispatchEvent(new Event(EXPLAINER_EVENT));
}

function HowThisWorks() {
  const hidden = useSyncExternalStore(subscribeExplainer, readExplainerHidden, () => false);
  return (
    <section className="ring-foreground/10 bg-card mb-6 ring-1" aria-labelledby="how-it-works-title">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        aria-expanded={!hidden}
        aria-controls="how-it-works-body"
        onClick={() => setExplainerHidden(!hidden)}
      >
        <span id="how-it-works-title" className="text-xs font-semibold">
          How this works
        </span>
        <span className="text-primary text-[11px]">{hidden ? "Show" : "Hide"}</span>
      </button>
      {!hidden && (
        <div id="how-it-works-body" className="border-border grid gap-4 border-t px-3 py-3 text-[11px] leading-relaxed md:grid-cols-2 xl:grid-cols-4">
          <div>
            <h3 className="mb-1 font-semibold">What is a data source?</h3>
            <p className="text-muted-foreground">
              A place the platform gets its information from: the public MESOB website, our own lists of documents and
              offices, selected legal texts, or a page or document your team adds with “Add data source”.
            </p>
          </div>
          <div>
            <h3 className="mb-1 font-semibold">What does a run do?</h3>
            <p className="text-muted-foreground">
              A run reads the source once and updates our copy of it. It happens in the background, so you can leave
              the page. Some sources run on a schedule; any source can be run by hand with “Run now”. Every run is
              recorded under Run history with who started it and what it changed.
            </p>
          </div>
          <div>
            <h3 className="mb-1 font-semibold">Where the data goes</h3>
            <ul className="text-muted-foreground space-y-1">
              {(["catalog", "graph", "knowledge"] as const).map((d) => (
                <li key={d}>
                  <span className="text-foreground font-medium">{DESTINATIONS[d].label}</span>: {DESTINATIONS[d].help}.
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="mb-1 font-semibold">What the statuses mean</h3>
            <dl className="text-muted-foreground space-y-1">
              {(
                [
                  ["success", undefined, "The last run finished and the data is up to date."],
                  ["failed", undefined, "The last run stopped with an error; nothing was changed. The reason is on the card."],
                  ["running", undefined, "A run is in progress. The page refreshes by itself."],
                  ["stuck", "warning", `Still “running” after ${STUCK_AFTER_MINUTES} minutes, so it has probably died. Use “Mark as failed”.`],
                  ["paused", "warning", "Turned off by staff. It won't run by hand or on its schedule until resumed."],
                  ["never run", "neutral", "Nobody has run it yet."],
                ] as const
              ).map(([status, tone, text]) => (
                <div key={status} className="flex items-start gap-2">
                  <dt className="shrink-0">
                    <StatusBadge status={status} tone={tone} />
                  </dt>
                  <dd>{text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- summary tiles

function SummaryStrip({ sources }: { sources: DataSource[] }) {
  const active = sources.filter((s) => s.enabled);
  const ran = active.filter((s) => s.lastRun);
  const failing = ran.filter((s) => isFailing(s.health));
  const paused = sources.filter((s) => !s.enabled);
  const runs = sources.reduce((n, s) => n + s.health.runs, 0);
  const ok = sources.reduce((n, s) => n + s.health.successes, 0);
  const bad = sources.reduce((n, s) => n + s.health.failures, 0);
  const lastFailure = sources
    .filter((s) => s.health.lastFailureAt)
    .sort((a, b) => (b.health.lastFailureAt ?? "").localeCompare(a.health.lastFailureAt ?? ""))[0];
  const neverRun = active.length - ran.length;
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      <StatTile
        label="Healthy"
        value={`${ran.length - failing.length} of ${active.length}`}
        hint={`Turned-on sources whose last finished run succeeded${neverRun ? ` · ${neverRun} never run` : ""}`}
      />
      <StatTile
        label="Failing"
        value={failing.length}
        hint={failing.length ? failing.map((s) => s.label).join(", ") : "Nothing failing"}
        tone={failing.length ? "attention" : "default"}
      />
      <StatTile
        label="Paused"
        value={paused.length}
        hint={paused.length ? paused.map((s) => s.label).join(", ") : "All sources are turned on"}
      />
      <StatTile label="Runs (30 days)" value={runs} hint={`${ok} successful · ${bad} failed, across all sources`} />
      <StatTile
        label="Success rate (30 days)"
        value={percent(ok + bad ? ok / (ok + bad) : null)}
        hint="Share of finished runs that ended without an error"
      />
      <StatTile
        label="Last failure"
        value={lastFailure ? timeAgo(lastFailure.health.lastFailureAt) : "None"}
        hint={lastFailure?.label ?? "No run has ever failed"}
      />
    </div>
  );
}

// ---------------------------------------------------------------- sources tab

function SourcesTab({ sources, runsHref }: { sources: DataSource[]; runsHref: (id: string) => string }) {
  // null: form closed · "new": adding · otherwise the custom source id being edited
  const [form, setForm] = useState<string | null>(null);
  const open = (value: string) => {
    setForm(value);
    requestAnimationFrame(() =>
      document.getElementById("source-form")?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  };
  const builtIn = sources.filter((s) => s.builtIn);
  const custom = sources.filter((s) => !s.builtIn);

  const grid = (list: DataSource[]) => (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {list.map((s) => (
        <SourceCard
          key={s.id}
          source={s}
          runsHref={runsHref(s.id)}
          onEdit={s.custom ? () => open(s.custom!.id) : undefined}
        />
      ))}
    </div>
  );

  return (
    <div className="space-y-8">
      <div id="source-form" className="scroll-mt-20">
        {form ? (
          <SourceForm
            editId={form === "new" ? null : form}
            onDone={(key) => {
              setForm(null);
              if (key) {
                requestAnimationFrame(() =>
                  document.getElementById(cardId(key))?.scrollIntoView({ behavior: "smooth", block: "start" }),
                );
              }
            }}
          />
        ) : (
          <div className="ring-foreground/10 flex flex-col gap-2 p-3 ring-1 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-muted-foreground text-[11px] leading-relaxed">
              Need the assistant to know about a new proclamation, directive or office notice? Add it as a data source:
              give us its web address (or paste its text) and we keep it in the AI knowledge base.
            </p>
            <Button size="sm" className="shrink-0" onClick={() => open("new")}>
              Add data source
            </Button>
          </div>
        )}
      </div>

      <section aria-labelledby="builtin-title">
        <h2 id="builtin-title" className="mb-1 text-sm font-semibold">
          Built-in pipelines ({builtIn.length})
        </h2>
        <p className="text-muted-foreground mb-3 text-[11px]">
          Part of the platform. They can be run, paused and resumed, but not edited or deleted.
        </p>
        {grid(builtIn)}
      </section>

      <section aria-labelledby="custom-title">
        <h2 id="custom-title" className="mb-1 text-sm font-semibold">
          Added by staff ({custom.length})
        </h2>
        <p className="text-muted-foreground mb-3 text-[11px]">
          Official pages and documents your team added. Each one feeds the AI knowledge base.
        </p>
        {custom.length ? (
          grid(custom)
        ) : (
          <p className="text-muted-foreground border-border border border-dashed p-4 text-center text-[11px]">
            None yet. Use “Add data source” above to add the first one.
          </p>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- page

export function DataSourcesPage() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const tab: Tab = params.get("tab") === "runs" ? "runs" : "sources";
  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ sources: null, runs: null });

  // Poll while anything is running; the first fetch decides
  const [poll, setPoll] = useState(false);
  const sources = useDataSources(poll);
  const runTotal = useDataSourceRunTotal(poll);

  const list = sources.payload?.sources ?? [];
  const anyRunning = list.some((s) => s.lastRun?.status === "running");
  if (anyRunning !== poll) setPoll(anyRunning);

  const selectTab = (next: Tab, focus = false) => {
    const sp = new URLSearchParams(params.toString());
    if (next === "runs") sp.set("tab", "runs");
    else sp.delete("tab");
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    if (focus) tabRefs.current[next]?.focus();
  };

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "sources", label: "Sources", count: sources.payload ? list.length : undefined },
    { id: "runs", label: "Run history", count: runTotal },
  ];

  const onKeyDown = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === tab);
    const moves: Record<string, number> = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 };
    if (!(e.key in moves)) return;
    e.preventDefault();
    selectTab(tabs[(moves[e.key] + tabs.length) % tabs.length].id, true);
  };

  /** Run history filtered to one source (other filters cleared). */
  const runsHref = (id: string) => `${pathname}?${new URLSearchParams({ tab: "runs", source: id })}`;

  return (
    <AdminPage
      title="Data sources"
      description="Where the platform's information comes from and how fresh it is: the MESOB service catalog, the knowledge graph used for roadmaps, the AI assistant's knowledge base, daily housekeeping, and any official pages your team adds."
    >
      {sources.isLoading ? (
        <LoadingState />
      ) : sources.error ? (
        <ErrorState error={sources.error} message={getErrorMessage(sources.error)} onRetry={() => sources.refetch()} />
      ) : (
        <>
          <SummaryStrip sources={list} />
          <HowThisWorks />
          <div
            role="tablist"
            aria-label="Data sources and run history"
            className="border-border mb-4 flex gap-1 overflow-x-auto overflow-y-hidden border-b [scrollbar-width:none]"
            onKeyDown={onKeyDown}
          >
            {tabs.map((t) => (
              <button
                key={t.id}
                ref={(el) => {
                  tabRefs.current[t.id] = el;
                }}
                id={`ds-tab-${t.id}`}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                aria-controls={`ds-panel-${t.id}`}
                tabIndex={tab === t.id ? 0 : -1}
                onClick={() => selectTab(t.id)}
                className={cn(
                  "-mb-px shrink-0 border-b-2 border-transparent px-3 py-2 text-xs",
                  tab === t.id ? "border-primary font-medium" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {t.label}
                {t.count != null && (
                  <span className="text-muted-foreground tabular-nums"> ({t.count.toLocaleString("en")})</span>
                )}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`ds-panel-${tab}`} aria-labelledby={`ds-tab-${tab}`} tabIndex={0} className="outline-none">
            {tab === "sources" ? <SourcesTab sources={list} runsHref={runsHref} /> : <RunHistory sources={list} poll={poll} />}
          </div>
        </>
      )}
    </AdminPage>
  );
}
