"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@cn/ui/card";
import { useGraphStats, useGraphView } from "@cn/core/api/admin";
import { getErrorMessage } from "@cn/core/lib/errors";
import { humanize } from "@cn/core/lib/format";
import { AdminPage } from "@/modules/components/admin-page";
import { StatTile } from "@/modules/shared/stat-tile";
import { ErrorState, EmptyState, LoadingState } from "@/modules/shared/states";
import { CypherConsole } from "@/modules/graph/cypher-console";
import { DocumentEditor } from "@/modules/graph/document-editor";
import { DocumentsTable } from "@/modules/graph/documents-table";
import { GraphExplorer } from "@/modules/graph/graph-explorer";

/** Plain-language explanation of the page for staff who are not engineers. */
function AboutGraph() {
  return (
    <details className="border-border bg-muted/20 mb-6 border p-3 text-xs leading-relaxed" open>
      <summary className="cursor-pointer font-medium">What is this page?</summary>
      <div className="mt-2 grid gap-4 md:grid-cols-3">
        <section>
          <h2 className="mb-1 font-semibold">What the graph is</h2>
          <p className="text-muted-foreground">
            A map of the government paperwork the app knows about. Each box is a document (like a Kebele ID), a goal
            a citizen can ask for (like a trade license), a business sector, or a service an organization published.
            Each arrow means &ldquo;you need this first&rdquo;: it points from what must be done before to what
            depends on it. So the left side holds the first steps and the right side holds the goals.
          </p>
        </section>
        <section>
          <h2 className="mb-1 font-semibold">How roadmaps use it</h2>
          <p className="text-muted-foreground">
            When a citizen asks for a goal, the app starts at the goal&rsquo;s final document and follows the
            arrows back to collect every document needed before it, skips the ones the citizen already has, and
            puts the rest in order. Fees and days on each document become the roadmap&rsquo;s cost and time. A
            sector adds its extra permits. If a box here is wrong, every roadmap that passes through it is wrong.
          </p>
        </section>
        <section>
          <h2 className="mb-1 font-semibold">What &ldquo;stale&rdquo; means</h2>
          <p className="text-muted-foreground">
            A document is stale when nobody has checked its fee, time and requirements against the official
            source for 30 days. Stale items have an amber border. To fix one: open it, compare each fact with
            the official source (or a MESOB center), correct what changed, tick &ldquo;I checked these
            facts&rdquo; and save. The daily maintenance job in{" "}
            <Link href="/data-sources" className="text-primary underline">
              Data sources
            </Link>{" "}
            flags documents again when they get old.
          </p>
        </section>
      </div>
    </details>
  );
}

export function GraphPage() {
  const stats = useGraphStats();
  const view = useGraphView();
  const [editingId, setEditingId] = useState<string | null>(null);
  const closeEditor = useCallback(() => setEditingId(null), []);
  const s = stats.payload;

  return (
    <AdminPage
      title="Knowledge graph"
      description="The map behind every roadmap: which documents each goal needs, in what order, where each can be done at MESOB, and how recently the facts were checked."
    >
      <AboutGraph />

      {stats.isLoading ? (
        <LoadingState />
      ) : stats.error || !s ? (
        <ErrorState message={getErrorMessage(stats.error, "The graph database (Neo4j) is not reachable")} onRetry={() => stats.refetch()} />
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Items in the database" value={s.totalNodes} hint={`${Object.keys(s.nodes).length} kinds`} />
          <StatTile label="Links" value={s.totalRelationships} hint={`${Object.keys(s.relationships).length} kinds`} />
          <StatTile
            label="Stale documents"
            value={s.staleDocuments}
            tone={s.staleDocuments ? "attention" : "default"}
            hint="Not checked in 30 days"
          />
          <StatTile label="MESOB services" value={s.nodes.GovService ?? 0} hint={`${s.nodes.Institution ?? 0} institutions`} />
          <div className="col-span-2 md:col-span-4">
            <details className="text-xs">
              <summary className="text-muted-foreground cursor-pointer">Counts by kind of item and link</summary>
              <div className="mt-2 grid gap-4 sm:grid-cols-2">
                {[s.nodes, s.relationships].map((group, i) => (
                  <dl key={i} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-0.5">
                    {Object.entries(group).map(([k, v]) => (
                      <div key={k} className="contents">
                        <dt className="text-muted-foreground">{i === 0 ? k : humanize(k.toLowerCase())}</dt>
                        <dd className="text-right tabular-nums">{v.toLocaleString("en")}</dd>
                      </div>
                    ))}
                  </dl>
                ))}
              </div>
            </details>
          </div>
        </div>
      )}

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Compliance dependency graph</CardTitle>
          <CardDescription>
            Read it left to right: Step 1 holds what can be done first, each later step needs something from an
            earlier one. Click an item to light up what it needs (blue) and what needs it (orange).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {view.isLoading ? (
            <LoadingState />
          ) : view.error || !view.payload ? (
            <ErrorState message={getErrorMessage(view.error)} onRetry={() => view.refetch()} />
          ) : !view.payload.nodes.length ? (
            <EmptyState title="The graph is empty" description="Run “Compliance dependency graph” under Data sources." />
          ) : (
            <GraphExplorer view={view.payload} onEdit={setEditingId} />
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Documents</CardTitle>
          <CardDescription>
            Correct fees, times and checklists here. Pick &ldquo;Stale&rdquo; to see what needs checking first.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DocumentsTable onEdit={setEditingId} />
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Cypher console (read-only)</CardTitle>
          <CardDescription>Ask the graph database questions directly</CardDescription>
        </CardHeader>
        <CardContent>
          <CypherConsole />
        </CardContent>
      </Card>

      {editingId && <DocumentEditor key={editingId} docId={editingId} onClose={closeEditor} />}
    </AdminPage>
  );
}
