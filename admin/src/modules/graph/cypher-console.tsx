"use client";

import { useState } from "react";
import { Button } from "@cn/ui/button";
import { Textarea } from "@cn/ui/textarea";
import { useCypherQuery } from "@cn/core/api/admin";
import { getErrorMessage } from "@cn/core/lib/errors";
import type { CypherResult } from "@cn/core/types/admin";
import { EmptyState } from "@/modules/shared/states";

const EXAMPLES = [
  {
    label: "Path to a trade license",
    query: "MATCH p = (d:Document)-[:REQUIRES*]->(:Document {id: 'trade_license'})\nRETURN [n IN nodes(p) | n.name] AS path",
  },
  {
    label: "Stale documents",
    query: "MATCH (d:Document) WHERE d.stale = true\nRETURN d.id AS id, d.name AS name, d.last_verified AS last_verified",
  },
  {
    label: "Services per institution",
    query: "MATCH (g:GovService {language: 'en'})-[:OFFERED_BY]->(i:Institution)\nRETURN i.short_name AS institution, count(g) AS services ORDER BY services DESC",
  },
  {
    label: "Free MESOB services",
    query: "MATCH (g:GovService {language: 'en'}) WHERE g.fee_etb_max = 0\nRETURN g.name AS service, g.processing_time_text AS time LIMIT 25",
  },
];

function cell(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function CypherConsole() {
  const { runQuery, isPending } = useCypherQuery();
  const [query, setQuery] = useState(EXAMPLES[0].query);
  const [result, setResult] = useState<CypherResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setError(null);
    try {
      setResult(await runQuery(query));
    } catch (e) {
      setResult(null);
      setError(getErrorMessage(e, "Query failed"));
    }
  };

  const rows = result?.rows ?? null;
  const columns = rows?.length ? Object.keys(rows[0]) : [];

  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-xs leading-relaxed">
        For staff who know Cypher, the graph query language. It can only read: anything that changes data, reads
        files or web links (LOAD CSV), or runs admin, APOC or dbms commands is refused before it reaches the
        database, and the database itself runs the query in read-only mode. A query stops after 10 seconds and
        shows at most 200 rows. Every query is logged with your name. To change data, use the documents table
        above or Data sources.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.label}
            type="button"
            className="border-border hover:bg-muted border px-2 py-1 text-[11px]"
            onClick={() => setQuery(ex.query)}
          >
            {ex.label}
          </button>
        ))}
      </div>
      <Textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        rows={4}
        spellCheck={false}
        className="font-mono text-xs"
        aria-label="Cypher query"
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run();
        }}
      />
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={run} loading={isPending} disabled={query.trim().length < 6}>
          Run query
        </Button>
        <span className="text-muted-foreground text-[11px]">Ctrl + Enter</span>
      </div>
      {error && (
        <p role="alert" className="text-destructive text-xs break-words">
          {error}
        </p>
      )}
      {rows &&
        (rows.length === 0 ? (
          <EmptyState title="No rows returned" />
        ) : (
          <div className="max-h-96 overflow-auto">
            <p className="text-muted-foreground mb-1 text-[11px]" aria-live="polite">
              {rows.length} row{rows.length === 1 ? "" : "s"}
              {result?.truncated && ` shown, there are more. Add LIMIT or a WHERE filter to narrow it down.`}
            </p>
            <table className="w-full text-left font-mono text-[11px]">
              <thead className="text-muted-foreground">
                <tr>
                  {columns.map((c) => (
                    <th key={c} className="py-1.5 pr-3 font-medium">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-border border-t align-top">
                    {columns.map((c) => (
                      <td key={c} className="max-w-xs py-1.5 pr-3 break-words">
                        {cell(r[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
    </div>
  );
}
