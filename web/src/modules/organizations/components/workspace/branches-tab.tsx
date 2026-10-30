"use client";

import type { MemberOrganization } from "@cn/core/types/organizations";
import { BranchesManager } from "@/modules/organizations/components/branch-editor";
import { Panel } from "@cn/ui/organizations/shared";

export function BranchesTab({ org }: { org: MemberOrganization }) {
  return (
    <Panel title="Branches" am="ቅርንጫፎች">
      <BranchesManager orgId={org.id} branches={org.branches ?? []} />
    </Panel>
  );
}
