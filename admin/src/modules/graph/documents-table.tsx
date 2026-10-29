"use client";

import { useEffect, useId, useState } from "react";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Pager } from "@cn/ui/pager";
import { GRAPH_DOCUMENTS_PAGE_SIZE, useGraphDocuments } from "@cn/core/api/admin";
import { formatDate } from "@cn/core/lib/format";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { NativeSelect } from "@/modules/shared/native-select";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { StatusBadge } from "@/modules/shared/status-badge";
import { formatFee } from "@/modules/graph/graph-style";

/** Documents in the graph, searched, filtered and paged on the server. */
export function DocumentsTable({ onEdit, initialStatus = "" }: { onEdit: (docId: string) => void; initialStatus?: string }) {
  const uid = useId();
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState(initialStatus);
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(GRAPH_DOCUMENTS_PAGE_SIZE);
  const docs = useGraphDocuments({ q, status, page, size });

  // Search after the admin stops typing, and go back to the first page
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(input.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [input]);

  const items = docs.payload?.items ?? [];
  const total = docs.payload?.total ?? 0;

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex flex-1 flex-col gap-1.5">
          <Label htmlFor={`${uid}-q`}>Search documents</Label>
          <Input
            id={`${uid}-q`}
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Name, id or issuing office"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${uid}-status`}>Status</Label>
          <NativeSelect
            id={`${uid}-status`}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All</option>
            <option value="verified">Verified</option>
            <option value="stale">Stale (needs checking)</option>
          </NativeSelect>
        </div>
      </div>

      {docs.isLoading ? (
        <LoadingState />
      ) : docs.error ? (
        <ErrorState message={getErrorMessage(docs.error)} onRetry={() => docs.refetch()} />
      ) : !items.length ? (
        <EmptyState
          title={q || status ? "No documents match" : "No documents in the graph"}
          description={q || status ? "Try other words or another status." : "Run “Compliance dependency graph” under Data sources."}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-xs">
            <caption className="sr-only">Documents in the knowledge graph</caption>
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th scope="col" className="w-56 py-2 pr-3 font-medium">Document</th>
                <th scope="col" className="w-44 py-2 pr-3 font-medium">Status</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Fee</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Days</th>
                <th scope="col" className="py-2 pr-3 font-medium">Needed first</th>
                <th scope="col" className="w-64 py-2 pr-3 font-medium">MESOB services</th>
                <th scope="col" className="py-2 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className={cn(docs.isFetching && "opacity-60")}>
              {items.map((d) => (
                <tr key={d.id} className="border-border border-t align-top">
                  <td className="py-2 pr-3">
                    <p className="font-medium">{d.name}</p>
                    <p className="text-muted-foreground text-[11px]">{d.issuing_authority ?? "Office unknown"}</p>
                  </td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={d.stale ? "stale" : "verified"} tone={d.stale ? "warning" : "good"} />
                    <p className="text-muted-foreground mt-0.5 text-[11px]">
                      {d.last_verified ? `Checked ${formatDate(d.last_verified)}` : "Never checked"}
                      {d.verified_by && <span className="block truncate">by {d.verified_by}</span>}
                    </p>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{d.fee_etb == null ? "-" : formatFee(d.fee_etb)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{d.avg_processing_days ?? "-"}</td>
                  <td className="text-muted-foreground py-2 pr-3">
                    {d.prerequisites.length
                      ? d.prerequisites.map((p) => d.prerequisite_names?.[p] ?? p).join(", ")
                      : "Nothing"}
                  </td>
                  <td className="py-2 pr-3">
                    {d.mesob_services.length ? (
                      <ul className="space-y-0.5">
                        {d.mesob_services.map((s) => (
                          <li key={s.id} className="max-w-64 truncate" title={s.name}>
                            {s.name}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-muted-foreground">Not linked</span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    <Button size="sm" variant="outline" onClick={() => onEdit(d.id)} aria-label={`Edit ${d.name}`}>
                      Edit
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={page} pageSize={size} total={total} onPage={setPage} onPageSize={(n) => { setSize(n); setPage(0); }} />
    </div>
  );
}
