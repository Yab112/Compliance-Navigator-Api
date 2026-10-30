"use client";

import type { MemberOrganization } from "@cn/core/types/organizations";
import { BranchesManager } from "@/modules/organizations/components/branch-editor";
import { Panel } from "@cn/ui/organizations/shared";
import { StepActions } from "@/modules/organizations/components/join/step-actions";

export function BranchesStep({ org, onBack, onNext }: { org: MemberOrganization; onBack: () => void; onNext: () => void }) {
  const branches = org.branches ?? [];
  return (
    <Panel title="3. Branches" am="ቅርንጫፎች">
      <p className="text-muted-foreground mb-4 text-sm">
        Every place where people get your services, with the exact address, a landmark, phone and weekly hours including the
        lunch break. Paths send each person to the branch in their sub-city.
      </p>
      <BranchesManager orgId={org.id} branches={branches} />
      <StepActions onBack={onBack} next={onNext} nextLabel="Continue" disabled={branches.length === 0} />
      {branches.length === 0 && <p className="text-muted-foreground mt-2 text-xs">Add at least one branch to continue.</p>}
    </Panel>
  );
}
