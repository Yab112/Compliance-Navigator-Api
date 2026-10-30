"use client";

import { useState } from "react";
import { useRequirementOptions } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { Field, NativeSelect, useDebounced } from "@cn/ui/guday/shared";
import { APPLIES_TO_LABEL, type Requirement } from "@cn/core/types/organizations";
import { toKey, lines, num, type SectionProps } from "@/modules/organizations/components/service-form/model";

function RequirementLinker({ req, onChange }: { req: Requirement; onChange: (patch: Partial<Requirement>) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(req.name);
  const q = useDebounced(query.trim(), 300);
  const options = useRequirementOptions(q, open);
  const data = open ? options.data?.payload : undefined;
  const linked = req.issuing_service_id ? "Linked to the service that issues it" : req.document_id ? `Linked to known document "${req.document_id}"` : null;

  return (
    <div className="sm:col-span-2">
      {linked ? (
        <p className="text-primary text-xs">
          ✓ {linked}{" "}
          <button type="button" className="text-destructive ml-1" onClick={() => onChange({ issuing_service_id: null, document_id: null, kind: "document" })}>
            Unlink
          </button>
        </p>
      ) : (
        <button type="button" className="text-primary text-xs font-medium hover:underline" onClick={() => setOpen((v) => !v)}>
          {open ? "Close" : "Link to the organization or document that issues it (connects your service to theirs on the path)"}
        </button>
      )}
      {open && !linked && (
        <div className="bg-secondary/40 mt-2 rounded-md p-3">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search services and documents" aria-label="Search issuers" />
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-muted-foreground text-[11px] font-semibold uppercase">Services on the platform</p>
              <ul className="mt-1 space-y-1 text-sm">
                {(data?.services ?? []).map((s) => (
                  <li key={s.service_id}>
                    <button
                      type="button"
                      className="hover:text-primary text-left"
                      onClick={() => {
                        onChange({ issuing_service_id: s.service_id, document_id: null, kind: "prerequisite_service" });
                        setOpen(false);
                      }}
                    >
                      {s.name} <span className="text-muted-foreground text-xs">· {s.org_name}</span>
                    </button>
                  </li>
                ))}
                {data && !data.services.length && <li className="text-muted-foreground text-xs">No matching services yet</li>}
              </ul>
            </div>
            <div>
              <p className="text-muted-foreground text-[11px] font-semibold uppercase">Known documents</p>
              <ul className="mt-1 space-y-1 text-sm">
                {(data?.documents ?? []).map((d) => (
                  <li key={d.document_id}>
                    <button
                      type="button"
                      className="hover:text-primary text-left"
                      onClick={() => {
                        onChange({ document_id: d.document_id, issuing_service_id: null, kind: "document" });
                        setOpen(false);
                      }}
                    >
                      {d.name ?? d.document_id}
                      {d.issuing_authority && <span className="text-muted-foreground text-xs"> · {d.issuing_authority}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function DocumentsSection({ form, set }: SectionProps) {
  const update = (i: number, patch: Partial<Requirement>) => set({ requirements: form.requirements.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const add = () =>
    set({
      no_documents_required: false,
      requirements: [
        ...form.requirements,
        {
          key: toKey(`doc ${form.requirements.length + 1}`, form.requirements.map((r) => r.key)),
          kind: "document",
          name: "",
          required: "always",
          notes: "",
          original_or_copy: null,
          copies: null,
          notarized: false,
          translated: false,
          max_age_days: null,
          photo_specs: "",
          applies_to: null,
          alternatives: [],
        },
      ],
    });
  const remove = (i: number) => {
    const key = form.requirements[i].key;
    set({
      requirements: form.requirements.filter((_, j) => j !== i),
      questions: form.questions.map((q) => ({ ...q, rules: q.rules.map((r) => ({ ...r, add_requirements: r.add_requirements.filter((k) => k !== key) })) })),
    });
  };

  return (
    <div className="space-y-4">
      <p className="text-muted-foreground text-sm">
        Everything people must bring to the window. These become their checklist on every path that passes through your office.
      </p>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.no_documents_required} disabled={form.requirements.length > 0} onChange={(e) => set({ no_documents_required: e.target.checked })} />
        No documents are needed for this service
      </label>
      <ol className="space-y-4">
        {form.requirements.map((r, i) => (
          <li key={i} className="border-border grid gap-3 rounded-md border p-4 sm:grid-cols-2">
            <Field label={`Document ${i + 1}`} htmlFor={`r-name-${i}`} required>
              <Input id={`r-name-${i}`} value={r.name} placeholder="e.g. TIN certificate" onChange={(e) => update(i, { name: e.target.value })} />
            </Field>
            <Field label="When is it needed?" htmlFor={`r-req-${i}`} hint={r.required === "conditional" ? "An answer in section 3 adds it" : undefined}>
              <NativeSelect id={`r-req-${i}`} className="h-9" value={r.required} onChange={(e) => update(i, { required: e.target.value as Requirement["required"] })}>
                <option value="always">Always</option>
                <option value="conditional">Only in some cases</option>
              </NativeSelect>
            </Field>
            <Field label="Original or copy" htmlFor={`r-orig-${i}`}>
              <NativeSelect id={`r-orig-${i}`} className="h-9" value={r.original_or_copy ?? ""} onChange={(e) => update(i, { original_or_copy: (e.target.value || null) as Requirement["original_or_copy"] })}>
                <option value="">Not specified</option>
                <option value="original">Original</option>
                <option value="copy">Copy</option>
                <option value="both">Original and a copy</option>
              </NativeSelect>
            </Field>
            <Field label="Number of copies" htmlFor={`r-copies-${i}`}>
              <Input id={`r-copies-${i}`} type="number" min={1} value={r.copies ?? ""} onChange={(e) => update(i, { copies: num(e.target.value) })} />
            </Field>
            <Field label="Needed from" htmlFor={`r-applies-${i}`}>
              <NativeSelect id={`r-applies-${i}`} className="h-9" value={r.applies_to ?? ""} onChange={(e) => update(i, { applies_to: (e.target.value || null) as Requirement["applies_to"] })}>
                <option value="">The applicant (default)</option>
                {(Object.entries(APPLIES_TO_LABEL) as [NonNullable<Requirement["applies_to"]>, string][]).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l.charAt(0).toUpperCase() + l.slice(1)}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Must be issued within (days)" htmlFor={`r-age-${i}`} hint="e.g. 90 for documents from the last 3 months">
              <Input id={`r-age-${i}`} type="number" min={1} value={r.max_age_days ?? ""} onChange={(e) => update(i, { max_age_days: num(e.target.value) })} />
            </Field>
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm sm:col-span-2">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={!!r.notarized} onChange={(e) => update(i, { notarized: e.target.checked })} />
                Must be notarized
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={!!r.translated} onChange={(e) => update(i, { translated: e.target.checked })} />
                Needs an Amharic translation
              </label>
            </div>
            <Field label="Photo requirements" htmlFor={`r-photo-${i}`} hint="Only for photos: size, background, how recent">
              <Input id={`r-photo-${i}`} value={r.photo_specs ?? ""} onChange={(e) => update(i, { photo_specs: e.target.value })} placeholder="3x4 cm, white background" />
            </Field>
            <Field label="Accepted instead (one per line)" htmlFor={`r-alt-${i}`}>
              <Textarea id={`r-alt-${i}`} rows={2} value={(r.alternatives ?? []).join("\n")} onChange={(e) => update(i, { alternatives: lines(e.target.value) })} />
            </Field>
            <Field label="Notes" htmlFor={`r-notes-${i}`} className="sm:col-span-2">
              <Input id={`r-notes-${i}`} value={r.notes ?? ""} onChange={(e) => update(i, { notes: e.target.value })} />
            </Field>
            <RequirementLinker req={r} onChange={(patch) => update(i, patch)} />
            <div className="flex justify-end sm:col-span-2">
              <button type="button" className="text-destructive text-xs" onClick={() => remove(i)}>
                Remove document
              </button>
            </div>
          </li>
        ))}
      </ol>
      <Button type="button" variant="outline" onClick={add}>
        + Add a document
      </Button>
    </div>
  );
}
