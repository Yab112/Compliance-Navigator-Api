"use client";

import { Button } from "@/components/ui/button";
import type { GraphDocument } from "@/types/admin";
import { formatDate } from "@/modules/admin/shared/format";
import { StatusBadge } from "@/modules/admin/shared/status-badge";
import { cn } from "@/lib/utils";

type Props = {
  documents: GraphDocument[];
  highlightId: string | null;
  onEdit: (doc: GraphDocument) => void;
};

export function DocumentsTable({ documents, highlightId, onEdit }: Props) {
  const names = Object.fromEntries(documents.map((d) => [d.id, d.name]));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-left text-xs">
        <thead className="text-muted-foreground text-[11px]">
          <tr>
            <th className="w-52 py-2 pr-3 font-medium">Document</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 pr-3 text-right font-medium">Fee</th>
            <th className="py-2 pr-3 text-right font-medium">Days</th>
            <th className="py-2 pr-3 font-medium">Prerequisites</th>
            <th className="w-72 py-2 pr-3 font-medium">MESOB services</th>
            <th className="py-2 font-medium" />
          </tr>
        </thead>
        <tbody>
          {documents.map((d) => (
            <tr key={d.id} className={cn("border-border border-t align-top", highlightId === d.id && "bg-primary/5")}>
              <td className="py-2 pr-3">
                <p className="font-medium">{d.name}</p>
                <p className="text-muted-foreground text-[11px]">
                  {d.issuing_authority} · verified {formatDate(d.last_verified)}
                </p>
              </td>
              <td className="py-2 pr-3">
                <StatusBadge status={d.stale ? "stale" : "verified"} tone={d.stale ? "warning" : "good"} />
              </td>
              <td className="py-2 pr-3 text-right tabular-nums">
                {d.fee_etb == null ? "-" : d.fee_etb === 0 ? "Free" : `${d.fee_etb.toLocaleString("en")} ETB`}
              </td>
              <td className="py-2 pr-3 text-right tabular-nums">{d.avg_processing_days ?? "-"}</td>
              <td className="text-muted-foreground py-2 pr-3">
                {d.prerequisites.length ? d.prerequisites.map((p) => names[p] ?? p).join(", ") : "None"}
              </td>
              <td className="py-2 pr-3">
                {d.mesob_services.length ? (
                  <ul className="space-y-0.5">
                    {d.mesob_services.map((s) => (
                      <li key={s.id} className="max-w-72 truncate" title={s.name}>
                        {s.name}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-muted-foreground">Not linked</span>
                )}
              </td>
              <td className="py-2 text-right">
                <Button size="sm" variant="outline" onClick={() => onEdit(d)}>
                  Edit
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
