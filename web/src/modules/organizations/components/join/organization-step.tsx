"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  useOrgAction,
  useOrgUpload,
  useRegisterOrganization,
  type OrgRegistrationInput,
} from "@cn/core/api/organizations";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Field, NativeSelect } from "@cn/ui/guday/shared";
import type { MemberOrganization } from "@cn/core/types/organizations";
import { ORG_TYPE_OPTIONS, Panel } from "@cn/ui/organizations/shared";
import { StepActions, clean } from "@/modules/organizations/components/join/step-actions";

export function OrganizationStep({ org, onSaved }: { org?: MemberOrganization; onSaved: (id: string) => void }) {
  const router = useRouter();
  const register = useRegisterOrganization();
  const action = useOrgAction();
  const upload = useOrgUpload();
  const [form, setForm] = useState({
    name: org?.name ?? "",
    name_am: org?.name_am ?? "",
    org_type: org?.org_type ?? "sub_city_office",
    sector: org?.sector ?? "",
    description: org?.description ?? "",
    phone: org?.phone ?? "",
    email: org?.email ?? "",
    website: org?.website ?? "",
    region: org?.region ?? "Addis Ababa",
    hq_address: org?.hq_address ?? "",
  });
  const [logo, setLogo] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setError(null);
    setPending(true);
    const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, k === "name" || k === "org_type" ? v.trim() : clean(v)]));
    try {
      if (org) {
        await action.mutateAsync({ url: apiPaths.org.workspace(org.id), method: MTD.PATCH, body });
        if (logo) await upload(apiPaths.org.logo(org.id), "logo", logo);
        onSaved(org.id);
      } else {
        const created = await register({ ...(body as unknown as OrgRegistrationInput), draft: true, branches: [] }, null, logo);
        onSaved(created.id);
      }
    } catch (err) {
      setError(getErrorMessage(err, "Could not save"));
    } finally {
      setPending(false);
    }
  };

  return (
    <Panel title="1. Your organization" am="ተቋምዎ">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Organization name (English)" htmlFor="name" required>
          <Input id="name" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Bole Sub-city Trade Office" />
        </Field>
        <Field label="ስም (Amharic)" htmlFor="name-am">
          <Input id="name-am" value={form.name_am} onChange={(e) => set("name_am", e.target.value)} />
        </Field>
        <Field label="Type" htmlFor="type" required>
          <NativeSelect id="type" className="h-9" value={form.org_type} onChange={(e) => set("org_type", e.target.value)}>
            {ORG_TYPE_OPTIONS.filter(([v]) => v !== "other").concat(ORG_TYPE_OPTIONS.filter(([v]) => v === "other")).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Sector" htmlFor="sector" hint="e.g. trade, tax, civil registration, land, health">
          <Input id="sector" value={form.sector} onChange={(e) => set("sector", e.target.value)} />
        </Field>
        <Field label="What does your organization do?" htmlFor="description" className="sm:col-span-2">
          <Textarea id="description" rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} />
        </Field>
        <Field label="Public phone" htmlFor="phone">
          <Input id="phone" type="tel" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
        </Field>
        <Field label="Public email" htmlFor="email">
          <Input id="email" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
        </Field>
        <Field label="Website" htmlFor="website">
          <Input id="website" type="url" placeholder="https://" value={form.website} onChange={(e) => set("website", e.target.value)} />
        </Field>
        <Field label="Region or city" htmlFor="region">
          <Input id="region" value={form.region} onChange={(e) => set("region", e.target.value)} />
        </Field>
        <Field label="Head office address" htmlFor="hq" className="sm:col-span-2">
          <Input id="hq" value={form.hq_address} onChange={(e) => set("hq_address", e.target.value)} />
        </Field>
        <Field label="Logo" htmlFor="logo" hint="Optional · JPG, PNG or WEBP, max 5 MB">
          <Input id="logo" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setLogo(e.target.files?.[0] ?? null)} />
        </Field>
      </div>
      <StepActions
        onBack={() => router.push("/organizations")}
        backLabel="Back to organizations"
        next={() => void save()}
        pending={pending}
        disabled={form.name.trim().length < 3}
        error={error}
      />
    </Panel>
  );
}
