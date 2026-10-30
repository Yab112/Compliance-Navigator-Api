"use client";

import { useState } from "react";
import { useOrgAction } from "@cn/core/api/organizations";
import { Input } from "@cn/ui/input";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Field } from "@cn/ui/guday/shared";
import type { MemberOrganization } from "@cn/core/types/organizations";
import { Panel } from "@cn/ui/organizations/shared";
import { StepActions, clean } from "@/modules/organizations/components/join/step-actions";

export function StewardStep({ org, onBack, onNext }: { org: MemberOrganization; onBack: () => void; onNext: () => void }) {
  const action = useOrgAction();
  const [form, setForm] = useState({
    steward_name: org.steward_name ?? "",
    steward_role: org.steward_role ?? "",
    steward_phone: org.steward_phone ?? "",
    steward_email: org.steward_email ?? "",
  });
  const [commit, setCommit] = useState(!!org.data_commitment_at);
  const [error, setError] = useState<string | null>(null);
  const valid = form.steward_name.trim().length >= 3 && (form.steward_phone.trim() || form.steward_email.trim()) && commit;

  const save = async () => {
    setError(null);
    const body = { ...Object.fromEntries(Object.entries(form).map(([k, v]) => [k, clean(v)])), data_commitment: commit };
    try {
      await action.mutateAsync({ url: apiPaths.org.workspace(org.id), method: MTD.PATCH, body });
      onNext();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <Panel title="5. Keeping your data current" am="መረጃን ወቅታዊ ማድረግ">
      <div className="space-y-4">
        <p className="text-sm">
          When a fee, a document or a window changes, people on the platform must know before they travel. Name the person who
          updates your services here. We remind them every 90 days to confirm each service is still accurate.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" htmlFor="st-name" required>
            <Input id="st-name" value={form.steward_name} onChange={(e) => setForm({ ...form, steward_name: e.target.value })} />
          </Field>
          <Field label="Role" htmlFor="st-role">
            <Input id="st-role" value={form.steward_role} onChange={(e) => setForm({ ...form, steward_role: e.target.value })} placeholder="e.g. Customer service officer" />
          </Field>
          <Field label="Phone" htmlFor="st-phone" hint="A phone or an email is required">
            <Input id="st-phone" type="tel" value={form.steward_phone} onChange={(e) => setForm({ ...form, steward_phone: e.target.value })} />
          </Field>
          <Field label="Email" htmlFor="st-email">
            <Input id="st-email" type="email" value={form.steward_email} onChange={(e) => setForm({ ...form, steward_email: e.target.value })} />
          </Field>
        </div>
        <label className="bg-secondary/50 flex items-start gap-3 rounded-md p-4 text-sm">
          <input type="checkbox" className="mt-1" checked={commit} onChange={(e) => setCommit(e.target.checked)} />
          <span>
            We will update requirements and prices here before they change, and confirm all services every 90 days.
            <span className="text-muted-foreground block">መስፈርቶችና ዋጋዎች ከመቀየራቸው በፊት እዚህ እናዘምናለን፤ በየ90 ቀኑ ሁሉንም አገልግሎቶች እናረጋግጣለን።</span>
          </span>
        </label>
      </div>
      <StepActions onBack={onBack} next={() => void save()} pending={action.isPending} disabled={!valid} error={error} />
    </Panel>
  );
}
