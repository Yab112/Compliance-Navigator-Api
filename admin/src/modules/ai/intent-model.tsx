"use client";

import { useState } from "react";
import { useAdminMutation, useAdminQuery } from "@cn/core/api/admin/use-admin-query";
import { Button } from "@cn/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@cn/ui/card";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { formatDateTime } from "@cn/core/lib/format";
import { NativeSelect } from "@/modules/shared/native-select";
import { StatTile } from "@/modules/shared/stat-tile";
import { ErrorState, LoadingState } from "@/modules/shared/states";
import { Pager } from "@cn/ui/pager";

const p = apiPaths.admin;

type Scores = { n: number; accuracy: number; macro_f1: number };
type Metrics = {
  version: string;
  chosen: string;
  created_at: string;
  featurizer: { kind: string; embedder: string | null };
  examples: Record<string, number>;
  test: Scores & { en?: Scores; amharic?: Scores; am_script?: Scores; transliterated?: Scores; per_intent: Record<string, number> };
  latency_ms: number;
  candidates: { name: string; val_score: number; test: Scores & { amharic?: Scores; en?: Scores }; latency_ms: number }[];
};
type ModelInfo = {
  active: string | null;
  metrics: Metrics | null;
  versions: { version: string; chosen: string | null; test: Scores | null; created_at: string | null }[];
  intents: string[];
  lastRun: { state: string; version?: string; activated?: boolean; test_macro_f1?: number; error?: string } | null;
  usage: { turns: number; turns_7d: number; low_confidence: number; labelled: number; conversations: number };
};
type Turn = {
  id: number;
  message_redacted: string;
  language: string | null;
  intent: string | null;
  confidence: number | null;
  resolved_service: string | null;
  labelled_intent: string | null;
  created_at: string;
};

const TURNS_PAGE_SIZE = 20;

const pct = (v?: number) => (v == null ? "-" : `${(v * 100).toFixed(1)}%`);

function TurnRow({ turn, intents }: { turn: Turn; intents: string[] }) {
  const { run, isPending } = useAdminMutation<unknown, { intent: string }>([["assistant"]]);
  const [intent, setIntent] = useState(turn.labelled_intent ?? turn.intent ?? "");
  const [saved, setSaved] = useState(!!turn.labelled_intent);
  const [error, setError] = useState<string | null>(null);
  return (
    <tr className="border-border border-t align-top">
      <td className="py-2 pr-3">
        <p className="text-sm break-words">{turn.message_redacted}</p>
        <p className="text-muted-foreground text-[11px]">
          {formatDateTime(turn.created_at)} · {turn.language ?? "?"} {turn.resolved_service ? `· ${turn.resolved_service}` : ""}
        </p>
      </td>
      <td className="py-2 pr-3 text-xs">
        {turn.intent ?? "-"} <span className="text-muted-foreground">({pct(turn.confidence ?? undefined)})</span>
      </td>
      <td className="py-2 pr-3">
        <NativeSelect value={intent} onChange={(e) => { setIntent(e.target.value); setSaved(false); }} aria-label="Correct intent">
          {!intent && <option value="">Pick one</option>}
          {intents.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </NativeSelect>
      </td>
      <td className="py-2 text-right">
        <Button
          size="sm"
          variant={saved ? "secondary" : "default"}
          disabled={isPending || !intent}
          onClick={async () => {
            setError(null);
            try {
              await run(p.assistantLabel(turn.id), MTD.POST, { intent });
              setSaved(true);
            } catch (e) {
              setError(getErrorMessage(e, "Couldn't save the label"));
            }
          }}
        >
          {saved ? "Labelled ✓" : "Save label"}
        </Button>
        {error && (
          <p role="alert" className="text-destructive mt-1 text-[11px]">
            {error}
          </p>
        )}
      </td>
    </tr>
  );
}

/** The trained intent model behind the assistant, and the loop that improves it. */
export function IntentModelSection() {
  const [polling, setPolling] = useState(false);
  const info = useAdminQuery<ModelInfo>(["assistant", "model"], p.assistantModel, { refetchInterval: polling ? 10000 : false });
  const [threshold, setThreshold] = useState("0.6");
  const [includeLabelled, setIncludeLabelled] = useState(false);
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(TURNS_PAGE_SIZE);
  const turnParams = new URLSearchParams({
    max_confidence: threshold,
    include_labelled: String(includeLabelled),
    limit: String(size),
    offset: String(page * size),
  });
  const turns = useAdminQuery<{ items: Turn[]; total: number }>(
    ["assistant", "turns", threshold, includeLabelled, page, size],
    `${p.assistantTurns}?${turnParams}`,
  );
  const retrain = useAdminMutation<{ started: boolean }, undefined>([["assistant"]]);
  const activate = useAdminMutation<{ active: string }, undefined>([["assistant"], ["ai-status"]]);
  const [message, setMessage] = useState<string | null>(null);
  const m = info.payload?.metrics;
  const running = info.payload?.lastRun?.state === "running";
  // Poll only while a training run is going, then stop
  if (running !== polling) setPolling(running);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Understanding model · intent classifier</CardTitle>
        <CardDescription>
          A small model trained on English, Amharic and Amharic typed in Latin letters decides what each message is
          asking for (its &ldquo;intent&rdquo;, such as asking for a roadmap or a fee). Facts in replies always come
          from the data, never from this model. Scores below are the share of test messages it understood correctly,
          balanced across intents (100% is perfect).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {m ? (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <StatTile label="Active version" value={m.version} hint={m.chosen} />
              <StatTile label="Overall score" value={pct(m.test.macro_f1)} hint={`macro-F1 on ${m.test.n} test messages`} />
              <StatTile label="English" value={pct(m.test.en?.macro_f1)} />
              <StatTile label="Amharic (all)" value={pct(m.test.amharic?.macro_f1)} hint={`script ${pct(m.test.am_script?.macro_f1)} · Latin ${pct(m.test.transliterated?.macro_f1)}`} />
              <StatTile label="Latency" value={`${m.latency_ms} ms`} hint="per message, CPU" />
              <StatTile label="Messages seen" value={info.payload?.usage.turns ?? 0} hint={`${info.payload?.usage.low_confidence ?? 0} low confidence · ${info.payload?.usage.labelled ?? 0} labelled`} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-xs">
                <thead className="text-muted-foreground">
                  <tr>
                    <th className="py-1.5 pr-3 font-medium">Candidate</th>
                    <th className="py-1.5 pr-3 font-medium">Validation</th>
                    <th className="py-1.5 pr-3 font-medium">Test macro-F1</th>
                    <th className="py-1.5 pr-3 font-medium">English</th>
                    <th className="py-1.5 pr-3 font-medium">Amharic</th>
                    <th className="py-1.5 font-medium">Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {m.candidates.map((c) => (
                    <tr key={c.name} className={c.name === m.chosen ? "bg-secondary/60 font-semibold" : "border-border border-t"}>
                      <td className="py-1.5 pr-3">{c.name}{c.name === m.chosen && " ✓"}</td>
                      <td className="py-1.5 pr-3">{c.val_score.toFixed(3)}</td>
                      <td className="py-1.5 pr-3">{pct(c.test.macro_f1)}</td>
                      <td className="py-1.5 pr-3">{pct(c.test.en?.macro_f1)}</td>
                      <td className="py-1.5 pr-3">{pct(c.test.amharic?.macro_f1)}</td>
                      <td className="py-1.5">{c.latency_ms} ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="text-muted-foreground text-sm">No model is trained yet. Press Retrain to train the first one.</p>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button
            disabled={running || retrain.isPending}
            onClick={async () => {
              setMessage(null);
              try {
                await retrain.run(p.assistantRetrain, MTD.POST);
                setMessage("Training started. It takes a few minutes; the new version is used only if it scores at least as well.");
              } catch (e) {
                setMessage(getErrorMessage(e));
              }
            }}
          >
            {running ? "Training…" : "Retrain with labelled messages"}
          </Button>
          {info.payload?.lastRun?.state === "done" && (
            <p className="text-muted-foreground text-xs">
              Last run: {info.payload.lastRun.version} · score {pct(info.payload.lastRun.test_macro_f1)} ·{" "}
              {info.payload.lastRun.activated ? "activated" : "kept the current model (no improvement)"}
            </p>
          )}
          {info.payload?.lastRun?.state === "failed" && <p className="text-destructive text-xs">Last run failed: {info.payload.lastRun.error}</p>}
          {message && (
            <p className="text-xs" role="status">
              {message}
            </p>
          )}
        </div>

        {(info.payload?.versions.length ?? 0) > 1 && (
          <details className="text-xs">
            <summary className="cursor-pointer font-medium">Trained versions ({info.payload?.versions.length})</summary>
            <p className="text-muted-foreground mt-1 mb-2">
              Switch back to an earlier version if the newest one answers worse in practice. The change is immediate.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-left">
                <thead className="text-muted-foreground text-[11px]">
                  <tr>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Version</th>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Method</th>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Score</th>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Trained</th>
                    <th scope="col" className="py-1.5"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {[...(info.payload?.versions ?? [])].reverse().map((v) => {
                    const active = v.version === info.payload?.active;
                    return (
                      <tr key={v.version} className="border-border border-t">
                        <td className="py-1.5 pr-3 font-mono">{v.version}</td>
                        <td className="py-1.5 pr-3">{v.chosen ?? "-"}</td>
                        <td className="py-1.5 pr-3 tabular-nums">{pct(v.test?.macro_f1)}</td>
                        <td className="py-1.5 pr-3">{v.created_at ? formatDateTime(v.created_at) : "-"}</td>
                        <td className="py-1.5 text-right">
                          {active ? (
                            <span className="text-muted-foreground">In use</span>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={activate.isPending || running}
                              onClick={async () => {
                                setMessage(null);
                                try {
                                  await activate.run(p.assistantActivate(v.version), MTD.POST);
                                  setMessage(`Now using ${v.version}.`);
                                } catch (e) {
                                  setMessage(getErrorMessage(e, "Couldn't switch versions"));
                                }
                              }}
                            >
                              Use this version
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        )}

        <div>
          <h3 className="mb-1 text-sm font-semibold">Messages the model was unsure about</h3>
          <p className="text-muted-foreground mb-2 text-xs">
            Pick the correct intent and save. Labelled messages join the training data on the next retrain. Long numbers
            (IDs, phones) are masked before anything is stored.
          </p>
          <div className="mb-3 flex flex-wrap items-end gap-4 text-xs">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="turns-threshold" className="text-[11px] font-medium">Show messages where the model was less than</label>
              <NativeSelect
                id="turns-threshold"
                value={threshold}
                onChange={(e) => {
                  setThreshold(e.target.value);
                  setPage(0);
                }}
              >
                <option value="0.4">40% sure</option>
                <option value="0.6">60% sure</option>
                <option value="0.8">80% sure</option>
                <option value="1">100% sure (everything)</option>
              </NativeSelect>
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeLabelled}
                onChange={(e) => {
                  setIncludeLabelled(e.target.checked);
                  setPage(0);
                }}
              />
              Include messages already labelled
            </label>
          </div>
          {turns.isLoading ? (
            <LoadingState />
          ) : turns.error ? (
            <ErrorState message={getErrorMessage(turns.error)} onRetry={() => turns.refetch()} />
          ) : turns.payload?.items.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left">
                <thead className="text-muted-foreground text-[11px]">
                  <tr>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Message</th>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Model said (how sure)</th>
                    <th scope="col" className="py-1.5 pr-3 font-medium">Correct intent</th>
                    <th scope="col" className="py-1.5"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {turns.payload.items.map((t) => (
                    <TurnRow key={t.id} turn={t} intents={info.payload?.intents ?? []} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">Nothing to review right now.</p>
          )}
          <Pager
            page={page}
            pageSize={size}
            total={turns.payload?.total ?? 0}
            onPage={setPage}
            onPageSize={(n) => { setSize(n); setPage(0); }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
