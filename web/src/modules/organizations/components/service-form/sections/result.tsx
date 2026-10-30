"use client";

import { useState } from "react";
import { useRequirementOptions } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Field, NativeSelect } from "@cn/ui/guday/shared";
import { type OrgServiceListItem } from "@cn/core/types/organizations";
import { num, type SectionProps } from "@/modules/organizations/components/service-form/model";

function OutputsField({ form, set }: SectionProps) {
  const [name, setName] = useState("");
  const options = useRequirementOptions("");
  const docs = options.data?.payload.documents ?? [];
  return (
    <div className="sm:col-span-2">
      <p className="text-xs font-medium">What people receive</p>
      <p className="text-muted-foreground mb-2 text-[11px]">
        Link it to a known document so every path that needs it, and every organization that requires it, points people to you.
      </p>
      <ul className="mb-2 space-y-1">
        {form.outputs.map((o, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{o.name}</span>
            <NativeSelect
              aria-label={`Known document for ${o.name}`}
              className="h-8 w-56"
              value={o.document_id ?? ""}
              onChange={(e) => set({ outputs: form.outputs.map((x, j) => (j === i ? { ...x, document_id: e.target.value || null } : x)) })}
            >
              <option value="">Not linked</option>
              {docs.map((d) => (
                <option key={d.document_id} value={d.document_id}>
                  {d.name ?? d.document_id}
                </option>
              ))}
            </NativeSelect>
            <button type="button" className="text-destructive text-xs" onClick={() => set({ outputs: form.outputs.filter((_, j) => j !== i) })}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Input placeholder="e.g. Trade license certificate" value={name} onChange={(e) => setName(e.target.value)} aria-label="Document this service issues" />
        <Button
          type="button"
          variant="outline"
          disabled={name.trim().length < 2}
          onClick={() => {
            set({ outputs: [...form.outputs, { name: name.trim(), document_id: null }] });
            setName("");
          }}
        >
          Add
        </Button>
      </div>
    </div>
  );
}

export function ResultSection({ form, set, services }: SectionProps & { services: OrgServiceListItem[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <OutputsField form={form} set={set} />
      <Field label="Valid for (months)" htmlFor="r-valid" hint="Leave empty if it doesn't expire. Used for renewal reminders">
        <Input id="r-valid" type="number" min={1} value={form.output_validity_months ?? ""} onChange={(e) => set({ output_validity_months: num(e.target.value) })} />
      </Field>
      <Field label="Renewal service" htmlFor="r-renew" hint="If renewal is a separate service">
        <NativeSelect id="r-renew" className="h-9" value={form.renewal_service_id ?? ""} onChange={(e) => set({ renewal_service_id: e.target.value || null })}>
          <option value="">Same service / not applicable</option>
          {services.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Penalty for late renewal" htmlFor="r-penalty" className="sm:col-span-2">
        <Input id="r-penalty" value={form.late_renewal_penalty ?? ""} onChange={(e) => set({ late_renewal_penalty: e.target.value })} />
      </Field>
      <Field label="Legal basis" htmlFor="r-legal" hint="Proclamation, regulation or directive">
        <Input id="r-legal" value={form.legal_basis ?? ""} onChange={(e) => set({ legal_basis: e.target.value })} />
      </Field>
      <Field label="Its number" htmlFor="r-legal-no" hint="e.g. 1150/2019">
        <Input id="r-legal-no" value={form.legal_reference_number ?? ""} onChange={(e) => set({ legal_reference_number: e.target.value })} />
      </Field>
      <Field label="In force since" htmlFor="r-legal-date">
        <Input id="r-legal-date" type="date" value={form.legal_effective_date ?? ""} onChange={(e) => set({ legal_effective_date: e.target.value || null })} />
      </Field>
      <div />
      <Field label="Contact for questions: name or desk" htmlFor="r-cname">
        <Input id="r-cname" value={form.contact_name ?? ""} onChange={(e) => set({ contact_name: e.target.value })} />
      </Field>
      <Field label="Contact phone" htmlFor="r-cphone">
        <Input id="r-cphone" value={form.contact_phone ?? ""} onChange={(e) => set({ contact_phone: e.target.value })} />
      </Field>
      <Field label="Contact email" htmlFor="r-cemail">
        <Input id="r-cemail" type="email" value={form.contact_email ?? ""} onChange={(e) => set({ contact_email: e.target.value })} />
      </Field>
    </div>
  );
}
