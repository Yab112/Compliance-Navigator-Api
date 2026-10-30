"use client";

import { useState } from "react";
import { useOrgAction, useOrgUpload } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Field, NativeSelect } from "@cn/ui/guday/shared";
import type { MemberOrganization } from "@cn/core/types/organizations";
import { ORG_TYPE_OPTIONS, OrgLogo, Panel } from "@cn/ui/organizations/shared";

export function ProfileTab({ org }: { org: MemberOrganization }) {
  const action = useOrgAction();
  const upload = useOrgUpload();
  const [form, setForm] = useState({
    name: org.name,
    name_am: org.name_am ?? "",
    org_type: org.org_type,
    sector: org.sector ?? "",
    description: org.description ?? "",
    phone: org.phone ?? "",
    email: org.email ?? "",
    website: org.website ?? "",
    hq_address: org.hq_address ?? "",
    region: org.region ?? "",
    representative_name: org.representative_name ?? "",
    representative_title: org.representative_title ?? "",
    official_email: org.official_email ?? "",
    steward_name: org.steward_name ?? "",
    steward_role: org.steward_role ?? "",
    steward_phone: org.steward_phone ?? "",
    steward_email: org.steward_email ?? "",
  });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const text = (k: keyof typeof form, label: string, extra?: React.ComponentProps<typeof Input>) => (
    <Field label={label} htmlFor={`p-${k}`}>
      <Input id={`p-${k}`} value={form[k]} onChange={(e) => set(k, e.target.value)} {...extra} />
    </Field>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <Panel title="Organization details" am="የተቋም መረጃ">
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={async (e) => {
            e.preventDefault();
            setMsg(null);
            const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]));
            try {
              await action.mutateAsync({ url: apiPaths.org.workspace(org.id), method: MTD.PATCH, body });
              setMsg({ ok: true, text: "Saved." });
            } catch (err) {
              setMsg({ ok: false, text: getErrorMessage(err) });
            }
          }}
        >
          {text("name", "Name (English)")}
          {text("name_am", "ስም (Amharic)")}
          <Field label="Type" htmlFor="p-type">
            <NativeSelect id="p-type" className="h-9" value={form.org_type} onChange={(e) => set("org_type", e.target.value)}>
              {ORG_TYPE_OPTIONS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </NativeSelect>
          </Field>
          {text("sector", "Sector")}
          <Field label="Description" htmlFor="p-desc" className="sm:col-span-2">
            <Textarea id="p-desc" rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} />
          </Field>
          {text("phone", "Public phone", { type: "tel" })}
          {text("email", "Public email", { type: "email" })}
          {text("website", "Website", { type: "url" })}
          {text("region", "Region / city")}
          {text("hq_address", "Head office address")}
          {text("representative_name", "Representative")}
          {text("representative_title", "Representative's position")}
          {text("official_email", "Official email", { type: "email" })}
          <p className="text-xs font-semibold sm:col-span-2">Who keeps your service data current</p>
          {text("steward_name", "Name")}
          {text("steward_role", "Role")}
          {text("steward_phone", "Phone", { type: "tel" })}
          {text("steward_email", "Email", { type: "email" })}
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" loading={action.isPending}>
              Save details
            </Button>
            {msg && <p className={msg.ok ? "text-primary text-sm" : "text-destructive text-sm"}>{msg.text}</p>}
          </div>
          <p className="text-muted-foreground text-xs sm:col-span-2">
            Changing the name or type of a verified organization sends it back for verification.
          </p>
        </form>
      </Panel>
      <div className="space-y-4">
        <Panel title="Logo">
          <OrgLogo name={org.name} url={org.logo_url} className="mb-3 size-20" />
          <Input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label="Upload logo"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) await upload(apiPaths.org.logo(org.id), "logo", file);
            }}
          />
        </Panel>
        <Panel title="Authorization letter">
          <p className="mb-3 text-sm">
            {org.has_authorization_letter ? "✓ Letter on file. Upload again to replace it." : "No letter uploaded yet. It speeds up verification."}
          </p>
          <Input
            type="file"
            accept="application/pdf,image/png,image/jpeg"
            aria-label="Upload authorization letter"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) await upload(apiPaths.org.letter(org.id), "letter", file);
            }}
          />
        </Panel>
      </div>
    </div>
  );
}
