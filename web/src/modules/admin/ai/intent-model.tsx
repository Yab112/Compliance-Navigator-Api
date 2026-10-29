"use client";

import { useState } from "react";
import { useAdminMutation, useAdminQuery } from "@/api/admin/use-admin-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiPaths } from "@/lib/constants/api-paths";
import { MTD } from "@/lib/constants/methods";
import { getErrorMessage } from "@/lib/errors";
import { formatDateTime } from "@/modules/admin/shared/format";
import { NativeSelect } from "@/modules/admin/shared/native-select";
import { StatTile } from "@/modules/admin/shared/stat-tile";

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

const pct = (v?: number) => (v == null ? "-" : `${(v * 100).toFixed(1)}%`);

function TurnRow({ turn, intents }: { turn: Turn; intents: string[] }) {
  const { run, isPending } = useAdminMutation<unknown, { intent: string }>();
  const [intent, setIntent] = useState(turn.labelled_intent ?? turn.intent ?? "");
  const [saved, setSaved] = useState(!!turn.labelled_intent);
  return (
    <tr className="border-border border-t align-top">
      <td className="py-2 pr-3">
        <p className="text-sm">{turn.message_redacted}</p>
        <p className="text-muted-foreground text-[11px]">
          {formatDateTime(turn.created_at)} · {turn.language ?? "?"} {turn.resolved_service ? `· ${turn.resolved_service}` : ""}
        </p>
      </td>
      <td className="py-2 pr-3 text-xs">
        {turn.intent ?? "-"} <span className="text-muted-foreground">({pct(turn.confidence ?? undefined)})</span>
      </td>
      <td className="py-2 pr-3">
        <NativeSelect value={intent} onChange={(e) => { setIntent(e.target.value); setSaved(false); }} aria-label="Correct intent">
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
            await run(p.assistantLabel(turn.id), MTD.POST, { intent });
            setSaved(true);
          }}
        >
          {saved ? "Labelled" : "Save label"}
        </Button>
      </td>
    </tr>
  );
}

/** The trained intent model behind the assistant, and the loop that improves it. */
export function IntentModelSection() {
  const info = useAdminQuery<ModelInfo>(["assistant", "model"], p.assistantModel, { refetchInterval: 15000 });
  const turns = useAdminQuery<{ turns: Turn[] }>(["assistant", "turns"], `${p.assistantTurns}?max_confidence=0.6&limit=30`);
  const retrain = useAdminMutation<{ started: boolean }, undefined>();
  const [message, setMessage] = useState<string | null>(null);
  const m = info.payload?.metrics;
  const running = info.payload?.lastRun?.state === "running";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Understanding model · intent classifier</CardTitle>
        <CardDescription>
          A small model trained on English, Amharic and transliterated Amharic decides what each message is asking for.
          Facts in replies always come from the data, never from the model.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {m ? (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <StatTile label="Active version" value={m.version} hint={m.chosen} />
              <StatTile label="Test macro-F1" value={pct(m.test.macro_f1)} hint={`${m.test.n} held-out messages`} />
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
              Last run: {info.payload.lastRun.version} · test macro-F1 {pct(info.payload.lastRun.test_macro_f1)} ·{" "}
              {info.payload.lastRun.activated ? "activated" : "kept the current model (no improvement)"}
            </p>
          )}
          {info.payload?.lastRun?.state === "failed" && <p className="text-destructive text-xs">Last run failed: {info.payload.lastRun.error}</p>}
          {message && <p className="text-xs">{message}</p>}
        </div>

        <div>
          <h3 className="mb-1 text-sm font-semibold">Messages the model was unsure about</h3>
          <p className="text-muted-foreground mb-2 text-xs">
            Pick the correct intent and save. Labelled messages join the training data on the next retrain. Long numbers
            (IDs, phones) are masked before anything is stored.
          </p>
          {turns.payload?.turns.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left">
                <thead className="text-muted-foreground text-[11px]">
                  <tr>
                    <th className="py-1.5 pr-3 font-medium">Message</th>
                    <th className="py-1.5 pr-3 font-medium">Model said</th>
                    <th className="py-1.5 pr-3 font-medium">Correct intent</th>
                    <th className="py-1.5" />
                  </tr>
                </thead>
                <tbody>
                  {turns.payload.turns.map((t) => (
                    <TurnRow key={t.id} turn={t} intents={info.payload?.intents ?? []} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">Nothing to review right now.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
