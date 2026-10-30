"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useOrgAction, useRegistrationCheck } from "@cn/core/api/organizations";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { LoadingState } from "@cn/ui/guday/shared";
import type { MemberOrganization } from "@cn/core/types/organizations";
import { CompletenessMeter, Panel } from "@cn/ui/organizations/shared";
import { StepActions } from "@/modules/organizations/components/join/step-actions";

export function ReviewStep({ org, onBack, onEdit }: { org: MemberOrganization; onBack: () => void; onEdit: (step: number) => void }) {
  const router = useRouter();
  const check = useRegistrationCheck(org.id);
  const action = useOrgAction();
  const [submitServices, setSubmitServices] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const problems = check.data?.payload.problems ?? [];
  const services = (check.data?.payload.services ?? []).filter((s) => s.status !== "archived");
  const isOwner = org.my_role === "owner" || org.my_role === "admin";

  const send = async () => {
    setError(null);
    try {
      await action.mutateAsync({ url: apiPaths.org.submitRegistration(org.id), method: MTD.POST, body: { submit_services: submitServices } });
      router.push(`/org/${org.id}`);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  if (check.isLoading) return <LoadingState />;
  const summary: [string, string, number][] = [
    ["Organization", `${org.name}${org.sector ? ` · ${org.sector}` : ""}`, 0],
    ["Representative", org.representative_name ? `${org.representative_name}, ${org.representative_title ?? ""}` : "Not given", 1],
    ["Authorization letter", org.has_authorization_letter ? "Uploaded" : "Not uploaded. Staff can't verify you without it", 1],
    ["Branches", `${org.branches?.length ?? 0}`, 2],
    ["Services", `${services.length}`, 3],
    ["Keeps the data current", org.steward_name ? `${org.steward_name}${org.data_commitment_at ? " · commitment given" : ""}` : "Not given", 4],
  ];

  return (
    <Panel title="6. Review and submit" am="ማጠቃለያ እና መላክ">
      <dl className="divide-border mb-5 divide-y text-sm">
        {summary.map(([label, value, step]) => (
          <div key={label} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <dt className="text-muted-foreground w-48">{label}</dt>
            <dd className="flex-1 font-medium">{value}</dd>
            <button type="button" className="text-primary text-xs hover:underline" onClick={() => onEdit(step)}>
              Change
            </button>
          </div>
        ))}
      </dl>
      {services.length > 0 && (
        <div className="mb-5">
          <p className="mb-2 text-sm font-semibold">How complete each service is</p>
          <ul className="space-y-3">
            {services.map((s) => (
              <li key={s.id}>
                <p className="text-sm">{s.name}</p>
                {s.completeness && <CompletenessMeter completeness={s.completeness} compact className="max-w-md" />}
              </li>
            ))}
          </ul>
          <label className="mt-4 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={submitServices} onChange={(e) => setSubmitServices(e.target.checked)} />
            Also send services that have the core details for review
          </label>
        </div>
      )}
      {problems.length > 0 && (
        <div className="mb-4 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-semibold">Still needed before sending:</p>
          <ul className="list-disc pl-5">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      {!isOwner && <p className="text-muted-foreground mb-2 text-sm">Only an owner of the organization can send the registration.</p>}
      <StepActions
        onBack={onBack}
        next={() => void send()}
        nextLabel="Send for verification"
        pending={action.isPending}
        disabled={problems.length > 0 || !isOwner}
        error={error}
      />
    </Panel>
  );
}
