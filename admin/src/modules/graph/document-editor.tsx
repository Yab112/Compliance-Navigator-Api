"use client";

import { useState } from "react";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Textarea } from "@cn/ui/textarea";
import { useUpdateDocument, type DocumentPatch } from "@cn/core/api/admin";
import { getErrorMessage } from "@cn/core/lib/errors";
import type { GraphDocument } from "@cn/core/types/admin";
import { formatDate } from "@cn/core/lib/format";

const lines = (v: string) => v.split("\n").map((l) => l.trim()).filter(Boolean);
const numOrNull = (v: string) => (v.trim() === "" ? null : Number(v));

export function DocumentEditor({ doc, onClose }: { doc: GraphDocument; onClose: () => void }) {
  const { updateDocument, isPending } = useUpdateDocument();
  const [form, setForm] = useState({
    issuing_authority: doc.issuing_authority ?? "",
    fee_etb: doc.fee_etb?.toString() ?? "",
    avg_processing_days: doc.avg_processing_days?.toString() ?? "",
    legal_basis: doc.legal_basis ?? "",
    source_url: doc.source_url ?? "",
    required_input_labels: (doc.required_input_labels ?? []).join("\n"),
    rejection_reasons: (doc.rejection_reasons ?? []).join("\n"),
    mark_verified: true,
  });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const fee = numOrNull(form.fee_etb);
    const days = numOrNull(form.avg_processing_days);
    if ((fee !== null && (Number.isNaN(fee) || fee < 0)) || (days !== null && (Number.isNaN(days) || days < 0))) {
      setError("Fee and processing days must be non-negative numbers.");
      return;
    }
    const body: DocumentPatch = {
      issuing_authority: form.issuing_authority,
      legal_basis: form.legal_basis || null,
      source_url: form.source_url || null,
      required_input_labels: lines(form.required_input_labels),
      rejection_reasons: lines(form.rejection_reasons),
      mark_verified: form.mark_verified,
    };
    if (fee !== null) body.fee_etb = fee;
    if (days !== null) body.avg_processing_days = days;
    try {
      await updateDocument(doc.id, body);
      onClose();
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't save the document"));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        className="bg-background border-border h-full w-full max-w-md overflow-y-auto border-l p-5"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={`Edit ${doc.name}`}
      >
        <div className="mb-4 flex items-start justify-between gap-2">
          <div>
            <p className="text-muted-foreground text-[11px]">Document · {doc.id}</p>
            <h2 className="text-base font-semibold">{doc.name}</h2>
            <p className="text-muted-foreground text-[11px]">Last verified {formatDate(doc.last_verified)}</p>
          </div>
          <Button size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
        <form className="flex flex-col gap-3" onSubmit={submit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ed-auth">Issuing authority</Label>
            <Input id="ed-auth" value={form.issuing_authority} onChange={set("issuing_authority")} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ed-fee">Fee (ETB)</Label>
              <Input id="ed-fee" inputMode="numeric" value={form.fee_etb} onChange={set("fee_etb")} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ed-days">Avg. processing days</Label>
              <Input id="ed-days" inputMode="numeric" value={form.avg_processing_days} onChange={set("avg_processing_days")} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ed-legal">Legal basis</Label>
            <Input id="ed-legal" value={form.legal_basis} onChange={set("legal_basis")} placeholder="e.g. Proc. 1396/2024" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ed-src">Source URL</Label>
            <Input id="ed-src" type="url" value={form.source_url} onChange={set("source_url")} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ed-inputs">Required inputs (one per line)</Label>
            <Textarea id="ed-inputs" rows={4} value={form.required_input_labels} onChange={set("required_input_labels")} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ed-reject">Common rejection reasons (one per line)</Label>
            <Textarea id="ed-reject" rows={3} value={form.rejection_reasons} onChange={set("rejection_reasons")} />
          </div>
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={form.mark_verified} onChange={set("mark_verified")} />
            Mark as verified today (clears the stale flag)
          </label>
          {error && <p className="text-destructive text-xs">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={isPending}>
              Save changes
            </Button>
          </div>
        </form>
      </aside>
    </div>
  );
}
