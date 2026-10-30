"use client";

import { useState } from "react";
import { useOrgAction, useOrgUpload } from "@cn/core/api/organizations";
import { Input } from "@cn/ui/input";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Field } from "@cn/ui/guday/shared";
import { useUserStore } from "@cn/core/store/user-store";
import type { MemberOrganization } from "@cn/core/types/organizations";
import { Panel } from "@cn/ui/organizations/shared";
import { StepActions } from "@/modules/organizations/components/join/step-actions";

export function RepresentativeStep({ org, onBack, onNext }: { org: MemberOrganization; onBack: () => void; onNext: () => void }) {
  const user = useUserStore((s) => s.user);
  const action = useOrgAction();
  const upload = useOrgUpload();
  const [form, setForm] = useState({
    representative_name: org.representative_name ?? user?.fullname ?? "",
    representative_title: org.representative_title ?? "",
    official_email: org.official_email ?? "",
  });
  const [letter, setLetter] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const valid = form.representative_name.trim().length >= 3 && form.representative_title.trim().length >= 2 && /\S+@\S+\.\S+/.test(form.official_email);

  const save = async () => {
    setError(null);
    try {
      await action.mutateAsync({ url: apiPaths.org.workspace(org.id), method: MTD.PATCH, body: form });
      if (letter) await upload(apiPaths.org.letter(org.id), "letter", letter);
      onNext();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <Panel title="2. Representative and authority" am="ተወካይ እና ሥልጣን">
      <div className="grid gap-4 sm:grid-cols-2">
        <p className="text-muted-foreground text-sm sm:col-span-2">
          We verify that the person registering may speak for the organization. Only the platform team sees these details.
        </p>
        <Field label="Your full name" htmlFor="rep-name" required>
          <Input id="rep-name" value={form.representative_name} onChange={(e) => setForm({ ...form, representative_name: e.target.value })} />
        </Field>
        <Field label="Your position" htmlFor="rep-title" required>
          <Input id="rep-title" value={form.representative_title} onChange={(e) => setForm({ ...form, representative_title: e.target.value })} placeholder="e.g. Head of customer service" />
        </Field>
        <Field label="Official work email" htmlFor="official-email" required hint="Use the organization's domain if it has one">
          <Input id="official-email" type="email" value={form.official_email} onChange={(e) => setForm({ ...form, official_email: e.target.value })} />
        </Field>
        <Field
          label="Authorization letter"
          htmlFor="letter"
          hint={org.has_authorization_letter ? "✓ Letter on file. Upload again to replace it." : "Signed and stamped letter naming you as the contact. PDF or image, max 5 MB"}
        >
          <Input id="letter" type="file" accept="application/pdf,image/png,image/jpeg" onChange={(e) => setLetter(e.target.files?.[0] ?? null)} />
        </Field>
      </div>
      <StepActions onBack={onBack} next={() => void save()} pending={action.isPending} disabled={!valid} error={error} />
    </Panel>
  );
}
