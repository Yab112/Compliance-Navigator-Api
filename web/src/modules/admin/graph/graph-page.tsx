"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useGraphDocuments, useGraphStats, useGraphView } from "@/api/admin";
import { getErrorMessage } from "@/lib/errors";
import { AdminPage } from "@/modules/admin/components/admin-page";
import { formatDate, humanize } from "@/modules/admin/shared/format";
import { StatTile } from "@/modules/admin/shared/stat-tile";
import { ErrorState, EmptyState, LoadingState } from "@/modules/admin/shared/states";
import type { GraphDocument } from "@/types/admin";
import { CypherConsole } from "./cypher-console";
import { DocumentEditor } from "./document-editor";
import { DocumentsTable } from "./documents-table";
import { GraphDiagram } from "./graph-diagram";
import type { PlacedNode } from "./graph-layout";

function NodeDetail({
  node,
  doc,
  mesob,
  onEdit,
}: {
  node: PlacedNode;
  doc?: GraphDocument;
  mesob: { id: string; name: string; institution?: string | null }[];
  onEdit: () => void;
}) {
  return (
    <div className="border-border bg-muted/30 mt-4 flex flex-col gap-2 border p-3 text-xs sm:flex-row sm:items-start sm:justify-between">
      <div className="space-y-1">
        <p className="text-muted-foreground text-[11px]">
          {node.type} · {node.id}
        </p>
        <p className="font-medium">{node.label}</p>
        {doc && (
          <p className="text-muted-foreground">
            {doc.fee_etb == null ? "Fee unknown" : doc.fee_etb === 0 ? "Free" : `${doc.fee_etb} ETB`} ·{" "}
            {doc.avg_processing_days ?? "?"} days · verified {formatDate(doc.last_verified)}
            {doc.stale && " · ▲ stale"}
          </p>
        )}
        {mesob.length > 0 && (
          <p>
            MESOB: {mesob.map((m) => `${m.name}${m.institution ? ` (${m.institution})` : ""}`).join("; ")}
          </p>
        )}
      </div>
      {doc && (
        <Button size="sm" onClick={onEdit}>
          Edit document
        </Button>
      )}
    </div>
  );
}

export function GraphPage() {
  const stats = useGraphStats();
  const view = useGraphView();
  const documents = useGraphDocuments();
  const [selected, setSelected] = useState<PlacedNode | null>(null);
  const [editing, setEditing] = useState<GraphDocument | null>(null);

  const docs = documents.payload?.documents ?? [];
  const selectedDoc = selected?.type === "Document" ? docs.find((d) => d.id === selected.id) : undefined;
  const selectedMesob =
    selected?.type === "Document" ? (view.payload?.mesobLinks ?? []).filter((l) => l.document === selected.id) : [];
  const s = stats.payload;

  return (
    <AdminPage
      title="Knowledge graph"
      description="The Neo4j compliance graph: which documents each service requires, in what order, where each can be done at MESOB, and how fresh the data is."
    >
      {stats.isLoading ? (
        <LoadingState />
      ) : stats.error || !s ? (
        <ErrorState message={getErrorMessage(stats.error, "Neo4j is unavailable")} onRetry={() => stats.refetch()} />
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Nodes" value={s.totalNodes} hint={`${Object.keys(s.nodes).length} labels`} />
          <StatTile label="Relationships" value={s.totalRelationships} hint={`${Object.keys(s.relationships).length} types`} />
          <StatTile label="Stale documents" value={s.staleDocuments} tone={s.staleDocuments ? "attention" : "default"} hint="Not verified in 30 days" />
          <StatTile label="MESOB services" value={s.nodes.GovService ?? 0} hint={`${s.nodes.Institution ?? 0} institutions`} />
          <div className="col-span-2 md:col-span-4">
            <details className="text-xs">
              <summary className="text-muted-foreground cursor-pointer">Counts by label and relationship type</summary>
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
            Prerequisites flow left to right. Services sit above the document they produce; sector-specific
            requirements sit below. Click a node for details.
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
            <>
              <GraphDiagram view={view.payload} selectedKey={selected?.key ?? null} onSelect={setSelected} />
              {selected && (
                <NodeDetail
                  node={selected}
                  doc={selectedDoc}
                  mesob={selectedMesob}
                  onEdit={() => selectedDoc && setEditing(selectedDoc)}
                />
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Documents</CardTitle>
          <CardDescription>Correct fees, timelines and checklists here; saving can mark a document verified.</CardDescription>
        </CardHeader>
        <CardContent>
          {documents.isLoading ? (
            <LoadingState />
          ) : documents.error ? (
            <ErrorState message={getErrorMessage(documents.error)} onRetry={() => documents.refetch()} />
          ) : !docs.length ? (
            <EmptyState title="No documents in the graph" />
          ) : (
            <DocumentsTable documents={docs} highlightId={selectedDoc?.id ?? null} onEdit={setEditing} />
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Cypher console</CardTitle>
          <CardDescription>Ask the graph questions directly</CardDescription>
        </CardHeader>
        <CardContent>
          <CypherConsole />
        </CardContent>
      </Card>

      {editing && <DocumentEditor key={editing.id} doc={editing} onClose={() => setEditing(null)} />}
    </AdminPage>
  );
}
