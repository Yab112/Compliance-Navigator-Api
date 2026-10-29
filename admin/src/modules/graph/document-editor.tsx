"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Textarea } from "@cn/ui/textarea";
import { useAdminQuery, useUpdateDocument, type DocumentPatch } from "@cn/core/api/admin";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import type { GraphDocument } from "@cn/core/types/admin";
import { formatDate } from "@cn/core/lib/format";
import { ErrorState, LoadingState } from "@/modules/shared/states";

// Same limits as the server (api/v1/admin/graph.py)
const MAX_FEE_ETB = 1_000_000;
const MAX_DAYS = 1_825;

const lines = (v: string) => v.split("\n").map((l) => l.trim()).filter(Boolean);

type Form = {
  name: string;
  name_am: string;
  issuing_authority: string;
  form_code: string;
  fee_etb: string;
  avg_processing_days: string;
  legal_basis: string;
  source_url: string;
  required_input_labels: string;
  rejection_reasons: string;
  mark_verified: boolean;
};
type Errors = Partial<Record<keyof Form, string>>;

function wholeNumber(value: string, max: number, what: string): string | undefined {
  if (value.trim() === "") return undefined;
  if (!/^\d+$/.test(value.trim())) return `${what} must be a whole number of 0 or more, without commas or letters.`;
  if (Number(value) > max) return `${what} looks too high (more than ${max.toLocaleString("en")}). Check it again.`;
  return undefined;
}

function validate(f: Form): Errors {
  const e: Errors = {};
  if (f.name.trim().length < 2) e.name = "Give the document a name.";
  const fee = wholeNumber(f.fee_etb, MAX_FEE_ETB, "The fee");
  if (fee) e.fee_etb = fee;
  const days = wholeNumber(f.avg_processing_days, MAX_DAYS, "Processing days");
  if (days) e.avg_processing_days = days;
  if (f.source_url.trim() && !/^https?:\/\/\S+$/.test(f.source_url.trim()))
    e.source_url = "The source link must start with http:// or https://";
  return e;
}

function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-muted-foreground text-[11px]">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-destructive text-[11px]">
          {error}
        </p>
      )}
    </div>
  );
}

function EditorForm({ doc, onClose }: { doc: GraphDocument; onClose: () => void }) {
  const { updateDocument, isPending } = useUpdateDocument();
  const [form, setForm] = useState<Form>({
    name: doc.name ?? "",
    name_am: doc.name_am ?? "",
    issuing_authority: doc.issuing_authority ?? "",
    form_code: doc.form_code ?? "",
    fee_etb: doc.fee_etb?.toString() ?? "",
    avg_processing_days: doc.avg_processing_days?.toString() ?? "",
    legal_basis: doc.legal_basis ?? "",
    source_url: doc.source_url ?? "",
    required_input_labels: (doc.required_input_labels ?? []).join("\n"),
    rejection_reasons: (doc.rejection_reasons ?? []).join("\n"),
    mark_verified: false,
  });
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const value = e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value;
    setForm((f) => ({ ...f, [k]: value }));
    if (errors[k]) setErrors((prev) => ({ ...prev, [k]: undefined }));
  };
  const a11y = (k: keyof Form, hint?: boolean) => ({
    "aria-invalid": errors[k] ? true : undefined,
    "aria-describedby": errors[k] ? `ed-${k}-error` : hint ? `ed-${k}-hint` : undefined,
  });

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    const found = validate(form);
    setErrors(found);
    const first = Object.keys(found)[0];
    if (first) {
      e.currentTarget.querySelector<HTMLElement>(`#ed-${first}`)?.focus();
      return;
    }
    const body: DocumentPatch = {
      name: form.name.trim(),
      name_am: form.name_am.trim() || null,
      issuing_authority: form.issuing_authority.trim(),
      form_code: form.form_code.trim() || null,
      legal_basis: form.legal_basis.trim() || null,
      source_url: form.source_url.trim() || null,
      required_input_labels: lines(form.required_input_labels),
      rejection_reasons: lines(form.rejection_reasons),
      mark_verified: form.mark_verified,
    };
    if (form.fee_etb.trim() !== "") body.fee_etb = Number(form.fee_etb);
    if (form.avg_processing_days.trim() !== "") body.avg_processing_days = Number(form.avg_processing_days);
    try {
      await updateDocument(doc.id, body);
      onClose();
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't save the document"));
    }
  };

  return (
    <>
      <div className="border-border mb-4 space-y-1 border p-2 text-[11px]">
        <p>
          <span className="text-muted-foreground">Last checked: </span>
          {doc.last_verified ? formatDate(doc.last_verified) : "never"}
          {doc.verified_by && <> by {doc.verified_by}</>}
          {doc.stale && <span className="text-amber-700 dark:text-amber-400"> · ▲ stale</span>}
        </p>
        {doc.updated_by && (
          <p>
            <span className="text-muted-foreground">Last edited: </span>
            {doc.updated_at ? formatDate(doc.updated_at) : ""} by {doc.updated_by}
          </p>
        )}
      </div>
      <form className="flex flex-col gap-3" onSubmit={submit} noValidate>
        <Field id="ed-name" label="Name (English)" error={errors.name}>
          <Input id="ed-name" value={form.name} onChange={set("name")} maxLength={200} {...a11y("name")} />
        </Field>
        <Field id="ed-name_am" label="Name (Amharic) · በአማርኛ">
          <Input id="ed-name_am" value={form.name_am} onChange={set("name_am")} maxLength={200} lang="am" />
        </Field>
        <Field id="ed-issuing_authority" label="Issuing office">
          <Input id="ed-issuing_authority" value={form.issuing_authority} onChange={set("issuing_authority")} maxLength={200} />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="ed-fee_etb" label="Fee (ETB)" error={errors.fee_etb} hint="Whole birr. 0 means free; empty keeps it unchanged.">
            <Input id="ed-fee_etb" inputMode="numeric" value={form.fee_etb} onChange={set("fee_etb")} {...a11y("fee_etb", true)} />
          </Field>
          <Field
            id="ed-avg_processing_days"
            label="Usual processing days"
            error={errors.avg_processing_days}
            hint="Working days from applying to collecting."
          >
            <Input
              id="ed-avg_processing_days"
              inputMode="numeric"
              value={form.avg_processing_days}
              onChange={set("avg_processing_days")}
              {...a11y("avg_processing_days", true)}
            />
          </Field>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="ed-form_code" label="Form code">
            <Input id="ed-form_code" value={form.form_code} onChange={set("form_code")} maxLength={60} />
          </Field>
          <Field id="ed-legal_basis" label="Legal basis">
            <Input id="ed-legal_basis" value={form.legal_basis} onChange={set("legal_basis")} maxLength={300} placeholder="e.g. Proc. 1396/2024" />
          </Field>
        </div>
        <Field id="ed-source_url" label="Official source link" error={errors.source_url}>
          <Input id="ed-source_url" type="url" value={form.source_url} onChange={set("source_url")} maxLength={500} {...a11y("source_url")} />
        </Field>
        <Field id="ed-required_input_labels" label="What the citizen must bring (one per line)">
          <Textarea id="ed-required_input_labels" rows={4} value={form.required_input_labels} onChange={set("required_input_labels")} />
        </Field>
        <Field id="ed-rejection_reasons" label="Common reasons it gets rejected (one per line)">
          <Textarea id="ed-rejection_reasons" rows={3} value={form.rejection_reasons} onChange={set("rejection_reasons")} />
        </Field>
        <label className="flex items-start gap-2 text-xs">
          <input type="checkbox" className="mt-0.5" checked={form.mark_verified} onChange={set("mark_verified")} />
          <span>
            I checked these facts against the official source today. Marks the document verified, records your name
            and clears the stale flag.
          </span>
        </label>
        {error && (
          <p role="alert" className="text-destructive text-xs">
            {error}
          </p>
        )}
        {Object.values(errors).some(Boolean) && (
          <p role="alert" className="text-destructive text-xs">
            Fix the highlighted fields and save again.
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={isPending}>
            Save changes
          </Button>
        </div>
      </form>
    </>
  );
}

/** Side sheet that loads one document fresh from the graph and edits it. */
export function DocumentEditor({ docId, onClose }: { docId: string; onClose: () => void }) {
  const doc = useAdminQuery<{ document: GraphDocument }>(["graph-document", docId], apiPaths.admin.graphDocument(docId));
  const closeRef = useRef<HTMLButtonElement>(null);
  const d = doc.payload?.document;

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        className="bg-background border-border h-full w-full max-w-md overflow-y-auto border-l p-5"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="doc-editor-title"
      >
        <div className="mb-4 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-muted-foreground text-[11px] break-all">Document · {docId}</p>
            <h2 id="doc-editor-title" className="text-base font-semibold break-words">
              {d ? `Edit ${d.name}` : "Edit document"}
            </h2>
          </div>
          <Button ref={closeRef} size="sm" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
        {doc.isLoading ? (
          <LoadingState />
        ) : doc.error || !d ? (
          <ErrorState message={getErrorMessage(doc.error, "Document not found")} onRetry={() => doc.refetch()} />
        ) : (
          <EditorForm key={d.id} doc={d} onClose={onClose} />
        )}
      </aside>
    </div>
  );
}
