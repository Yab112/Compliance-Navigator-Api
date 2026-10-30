"use client";

import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { Field, NativeSelect } from "@cn/ui/guday/shared";
import { AUDIENCE_LABEL, type Audience, type ServiceInput } from "@cn/core/types/organizations";
import { LANGUAGES, type SectionProps } from "@/modules/organizations/components/service-form/model";
import { Checks } from "@/modules/organizations/components/service-form/sections/shared";

export function AboutSection({ form, set }: SectionProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Service name (English)" htmlFor="s-name" required>
        <Input id="s-name" value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="e.g. New trade license" />
      </Field>
      <Field label="ስም (Amharic)" htmlFor="s-name-am">
        <Input id="s-name-am" value={form.name_am ?? ""} onChange={(e) => set({ name_am: e.target.value })} />
      </Field>
      <Field label="Summary" htmlFor="s-summary" required className="sm:col-span-2" hint="One or two sentences people see first on the path">
        <Textarea id="s-summary" rows={2} value={form.summary ?? ""} onChange={(e) => set({ summary: e.target.value })} />
      </Field>
      <Field label="Who can apply" htmlFor="s-who" className="sm:col-span-2" hint="e.g. Residents aged 18 or older registered in the woreda">
        <Textarea id="s-who" rows={2} value={form.who_can_apply ?? ""} onChange={(e) => set({ who_can_apply: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Checks
          label="Who the service is for"
          options={Object.entries(AUDIENCE_LABEL) as [Audience, string][]}
          value={form.audience}
          onChange={(audience) => set({ audience })}
        />
      </div>
      <Field label="How people apply" htmlFor="s-delivery">
        <NativeSelect id="s-delivery" className="h-9" value={form.delivery} onChange={(e) => set({ delivery: e.target.value as ServiceInput["delivery"] })}>
          <option value="in_person">In person at a branch</option>
          <option value="online">Online only</option>
          <option value="both">Online or in person</option>
        </NativeSelect>
      </Field>
      <Field label="Online application link" htmlFor="s-online">
        <Input id="s-online" type="url" value={form.online_url ?? ""} onChange={(e) => set({ online_url: e.target.value })} placeholder="https://" />
      </Field>
      <Field label="What can be done online" htmlFor="s-online-parts" className="sm:col-span-2" hint="e.g. Fill the form and book a slot online, then bring originals">
        <Input id="s-online-parts" value={form.online_parts ?? ""} onChange={(e) => set({ online_parts: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Checks label="Languages served at the window" options={LANGUAGES.map((l) => [l, l] as [string, string])} value={form.languages} onChange={(languages) => set({ languages })} />
      </div>
      <Field label="Accessibility" htmlFor="s-access" className="sm:col-span-2" hint="e.g. Ground floor window for people with limited mobility">
        <Input id="s-access" value={form.accessibility_notes ?? ""} onChange={(e) => set({ accessibility_notes: e.target.value })} />
      </Field>
    </div>
  );
}
