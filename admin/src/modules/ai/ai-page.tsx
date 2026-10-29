"use client";

import { IntentModelSection } from "@/modules/ai/intent-model";
import { useState } from "react";
import { Button } from "@cn/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@cn/ui/card";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Textarea } from "@cn/ui/textarea";
import { useAIStatus, useAITest, useKnowledgeSearch, useSaveAISettings } from "@cn/core/api/admin";
import { getErrorMessage } from "@cn/core/lib/errors";
import { AdminPage } from "@/modules/components/admin-page";
import { formatDateTime, humanize } from "@cn/core/lib/format";
import { NativeSelect } from "@/modules/shared/native-select";
import { StatTile } from "@/modules/shared/stat-tile";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { StatusBadge } from "@/modules/shared/status-badge";
import type { AIStatus, AITestResult, KnowledgeHit } from "@cn/core/types/admin";

const PROVIDER_INFO: Record<string, string> = {
  keyword: "Rule-based, instant and offline. Understands the main goals and sub-cities but can't hold a real conversation.",
  ollama: "Local open model on this server. On a CPU-only machine a reply can take ~60 seconds, and Amharic quality from small open models is weak.",
  anthropic: "Claude via the Anthropic API, best Amharic and reasoning quality. Requires ANTHROPIC_API_KEY in api/.env.",
};

function ProviderSettings({ status }: { status: AIStatus }) {
  const { saveSettings, isPending } = useSaveAISettings();
  const [provider, setProvider] = useState(status.provider);
  const [model, setModel] = useState(status.ollama.model);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const blocked =
    (provider === "anthropic" && !status.anthropic.configured) ||
    (provider === "ollama" && !status.ollama.reachable);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Assistant provider</CardTitle>
        <CardDescription>Switches take effect immediately for every chat.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ai-provider">Provider</Label>
          <NativeSelect id="ai-provider" value={provider} onChange={(e) => setProvider(e.target.value as AIStatus["provider"])}>
            {status.providers.map((p) => (
              <option key={p} value={p}>
                {humanize(p)}
              </option>
            ))}
          </NativeSelect>
          <p className="text-muted-foreground text-[11px] leading-relaxed">{PROVIDER_INFO[provider]}</p>
        </div>
        {provider === "ollama" && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ai-model">Ollama model</Label>
            {status.ollama.models.length ? (
              <NativeSelect id="ai-model" value={model} onChange={(e) => setModel(e.target.value)}>
                {!status.ollama.models.includes(model) && <option value={model}>{model} (not installed)</option>}
                {status.ollama.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </NativeSelect>
            ) : (
              <p className="text-destructive text-[11px]">No models found, is Ollama running at {status.ollama.baseUrl}?</p>
            )}
          </div>
        )}
        {provider === "anthropic" && !status.anthropic.configured && (
          <p className="text-[11px] text-amber-700 dark:text-amber-400">
            ▲ Add ANTHROPIC_API_KEY to api/.env and restart the API before switching.
          </p>
        )}
        {message && <p className={message.error ? "text-destructive text-xs" : "text-xs text-emerald-700 dark:text-emerald-400"}>{message.text}</p>}
        <Button
          loading={isPending}
          disabled={blocked || (provider === status.provider && (provider !== "ollama" || model === status.ollama.model))}
          onClick={async () => {
            setMessage(null);
            try {
              await saveSettings({ provider, ollama_model: provider === "ollama" ? model : undefined });
              setMessage({ text: `Assistant now uses ${humanize(provider)}.` });
            } catch (e) {
              setMessage({ text: getErrorMessage(e, "Couldn't save settings"), error: true });
            }
          }}
        >
          Save provider
        </Button>
      </CardContent>
    </Card>
  );
}

function TestAssistant() {
  const { testPrompt, isPending } = useAITest();
  const [message, setMessage] = useState("I want a trade license in Bole, I already have my kebele ID");
  const [result, setResult] = useState<AITestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Test the assistant</CardTitle>
        <CardDescription>Sends a message through the live chat pipeline (no history is saved).</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3} aria-label="Test message" />
        <Button
          loading={isPending}
          disabled={message.trim().length < 2}
          onClick={async () => {
            setError(null);
            setResult(null);
            try {
              setResult(await testPrompt(message));
            } catch (e) {
              setError(getErrorMessage(e, "Test failed"));
            }
          }}
        >
          {isPending ? "Waiting for reply…" : "Send"}
        </Button>
        {error && <p className="text-destructive text-xs">{error}</p>}
        {result && (
          <div className="border-border space-y-2 border p-3 text-xs">
            <p className="leading-relaxed whitespace-pre-wrap">{result.reply}</p>
            <dl className="text-muted-foreground grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px] sm:grid-cols-3">
              <div><dt className="inline">Provider: </dt><dd className="text-foreground inline">{humanize(result.provider)}</dd></div>
              <div><dt className="inline">Latency: </dt><dd className="text-foreground inline tabular-nums">{(result.latencyMs / 1000).toFixed(1)}s</dd></div>
              <div><dt className="inline">Intent: </dt><dd className="text-foreground inline">{humanize(result.intent)}</dd></div>
              <div><dt className="inline">Language: </dt><dd className="text-foreground inline">{result.language === "am" ? "Amharic" : "English"}</dd></div>
              <div><dt className="inline">Goal: </dt><dd className="text-foreground inline">{result.suggestedGoal ? humanize(result.suggestedGoal) : "-"}</dd></div>
              <div><dt className="inline">Sub-city: </dt><dd className="text-foreground inline">{result.suggestedSubCity ? humanize(result.suggestedSubCity) : "-"}</dd></div>
              <div><dt className="inline">Roadmap built: </dt><dd className="text-foreground inline">{result.roadmapBuilt ? "Yes" : "No"}</dd></div>
            </dl>
            {result.catalogMatches.length > 0 && (
              <div>
                <p className="text-muted-foreground mb-1 text-[11px]">MESOB services suggested</p>
                <ul className="list-inside list-disc">
                  {result.catalogMatches.map((m) => (
                    <li key={m.id}>
                      {m.name} <span className="text-muted-foreground">({m.institution})</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function KnowledgeSearch() {
  const { search, isPending } = useKnowledgeSearch();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<KnowledgeHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Search the knowledge base</CardTitle>
        <CardDescription>See exactly which passages the assistant can ground its answers in.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <form
          className="flex gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            setError(null);
            try {
              setHits((await search(query)).results);
            } catch (err) {
              setError(getErrorMessage(err, "Search failed"));
            }
          }}
        >
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. documents for passport renewal" aria-label="Knowledge base query" />
          <Button type="submit" loading={isPending} disabled={query.trim().length < 3}>
            Search
          </Button>
        </form>
        {error && <p className="text-destructive text-xs">{error}</p>}
        {hits &&
          (hits.length === 0 ? (
            <EmptyState title="No relevant passages" description="Try other words, or ingest more sources under Data sources." />
          ) : (
            <ul className="space-y-2">
              {hits.map((h) => (
                <li key={h.id} className="border-border border p-2 text-xs">
                  <div className="text-muted-foreground mb-1 flex flex-wrap items-center gap-x-3 text-[11px]">
                    <span className="text-foreground font-medium tabular-nums">{(h.similarity * 100).toFixed(0)}% match</span>
                    {h.issuing_body && <span>{h.issuing_body}</span>}
                    {h.service_id && <span>{h.service_id}</span>}
                  </div>
                  <p className="line-clamp-4 leading-relaxed">{h.content}</p>
                </li>
              ))}
            </ul>
          ))}
      </CardContent>
    </Card>
  );
}

export function AIPage() {
  const { payload: s, isLoading, error, refetch } = useAIStatus();

  return (
    <AdminPage
      title="AI assistant"
      description="The bilingual (English / Amharic) assistant behind chat: which model answers, what it knows, and a sandbox to try it."
    >
      {isLoading ? (
        <LoadingState />
      ) : error || !s ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <StatTile label="Active provider" value={humanize(s.provider)} />
            <StatTile
              label="Ollama"
              value={s.ollama.reachable ? "Reachable" : "Offline"}
              hint={s.ollama.reachable ? `${s.ollama.model}${s.ollama.modelInstalled ? "" : " (not installed)"}` : s.ollama.baseUrl}
              tone={s.provider === "ollama" && !s.ollama.reachable ? "attention" : "default"}
            />
            <StatTile label="Anthropic" value={s.anthropic.configured ? "Configured" : "No API key"} />
            <StatTile label="Knowledge chunks" value={s.knowledgeBase.total ?? "-"} hint={`${(s.knowledgeBase.mesob ?? 0).toLocaleString("en")} from MESOB`} />
            <StatTile label="Last ingest" value={s.knowledgeBase.last_ingested_at ? formatDateTime(s.knowledgeBase.last_ingested_at) : "-"} />
            <StatTile label="Speech to text" value={s.speechToText.model} hint={s.speechToText.engine} />
          </div>
          <p className="text-muted-foreground mt-2 text-[11px]">
            Embeddings: {s.embeddings.model} ({s.embeddings.dimension}-dim){" "}
            {s.knowledgeBase.error && <StatusBadge status="failed" className="ml-1" />}
          </p>
          <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,22rem)_1fr]">
            <ProviderSettings key={`${s.provider}:${s.ollama.model}`} status={s} />
            <TestAssistant />
          </div>
          <div className="mt-4">
            <IntentModelSection />
          </div>
          <div className="mt-4">
            <KnowledgeSearch />
          </div>
        </>
      )}
    </AdminPage>
  );
}
