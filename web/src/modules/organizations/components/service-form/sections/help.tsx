"use client";

import { useState } from "react";
import { useOrgUpload } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Field } from "@cn/ui/guday/shared";
import { lines, type SectionProps } from "@/modules/organizations/components/service-form/model";

export function HelpSection({ form, set, orgId }: SectionProps & { orgId: string }) {
  const upload = useOrgUpload();
  const [formError, setFormError] = useState<string | null>(null);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <p className="text-xs font-medium">Application forms (PDF)</p>
        <ul className="my-2 space-y-1 text-sm">
          {form.forms.map((f, i) => (
            <li key={i} className="flex items-center gap-2">
              <span>{f.title}</span>
              <button type="button" className="text-destructive text-xs" onClick={() => set({ forms: form.forms.filter((_, j) => j !== i) })}>
                Remove
              </button>
            </li>
          ))}
        </ul>
        <Input
          type="file"
          accept="application/pdf"
          aria-label="Upload a PDF form"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setFormError(null);
            try {
              const res = await upload<{ url: string; title: string }>(apiPaths.org.forms(orgId), "form", file);
              set({ forms: [...form.forms, { title: res.title.replace(/\.pdf$/i, ""), url: res.url }] });
            } catch (err) {
              setFormError(getErrorMessage(err));
            }
          }}
        />
        {formError && <p className="text-destructive mt-1 text-xs">{formError}</p>}
        <Field label="Fee notes" htmlFor="x-feenotes" className="mt-4">
          <Input id="x-feenotes" value={form.fee_notes ?? ""} onChange={(e) => set({ fee_notes: e.target.value })} />
        </Field>
      </div>
      <Field label="Why applications get sent back (one per line)" htmlFor="x-rej">
        <Textarea id="x-rej" rows={5} value={form.common_rejection_reasons.join("\n")} onChange={(e) => set({ common_rejection_reasons: lines(e.target.value) })} />
      </Field>
      <div className="lg:col-span-2">
        <p className="text-xs font-medium">Questions people ask</p>
        {form.faq.map((f, i) => (
          <div key={i} className="mt-2 space-y-1">
            <Input aria-label="Question" value={f.q} onChange={(e) => set({ faq: form.faq.map((x, j) => (j === i ? { ...x, q: e.target.value } : x)) })} />
            <Textarea aria-label="Answer" rows={2} value={f.a} onChange={(e) => set({ faq: form.faq.map((x, j) => (j === i ? { ...x, a: e.target.value } : x)) })} />
            <button type="button" className="text-destructive text-xs" onClick={() => set({ faq: form.faq.filter((_, j) => j !== i) })}>
              Remove
            </button>
          </div>
        ))}
        <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => set({ faq: [...form.faq, { q: "", a: "" }] })}>
          + Add question and answer
        </Button>
      </div>
    </div>
  );
}
