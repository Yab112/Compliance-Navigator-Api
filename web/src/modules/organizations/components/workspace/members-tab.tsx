"use client";

import { useState } from "react";
import { useOrgAction } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { NativeSelect } from "@cn/ui/guday/shared";
import type { MemberOrganization } from "@cn/core/types/organizations";
import { Panel } from "@cn/ui/organizations/shared";

export function MembersTab({ org }: { org: MemberOrganization }) {
  const action = useOrgAction();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"editor" | "owner">("editor");
  const [err, setErr] = useState<string | null>(null);
  const isOwner = org.my_role === "owner" || org.my_role === "admin";

  return (
    <Panel title="Team" am="ቡድን">
      <ul className="divide-border mb-4 divide-y">
        {(org.members ?? []).map((m) => (
          <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
            <div>
              <p className="font-medium break-words">{m.fullname || m.email}</p>
              <p className="text-muted-foreground text-xs">
                {m.email} · {m.role}
                {!m.accepted && " · invited, joins once they accept"}
              </p>
            </div>
            {isOwner && (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  action
                    .mutateAsync({ url: apiPaths.org.member(org.id, m.id), method: MTD.DELETE })
                    .catch((e) => setErr(getErrorMessage(e)))
                }
              >
                Remove
              </Button>
            )}
          </li>
        ))}
      </ul>
      {isOwner ? (
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={async (e) => {
            e.preventDefault();
            setErr(null);
            try {
              await action.mutateAsync({ url: apiPaths.org.members(org.id), method: MTD.POST, body: { email, role } });
              setEmail("");
            } catch (ex) {
              setErr(getErrorMessage(ex));
            }
          }}
        >
          <Input type="email" required placeholder="colleague@office.gov.et" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email to invite" />
          <NativeSelect className="h-9 sm:w-36" value={role} onChange={(e) => setRole(e.target.value as "editor" | "owner")} aria-label="Role">
            <option value="editor">Editor</option>
            <option value="owner">Owner</option>
          </NativeSelect>
          <Button type="submit" loading={action.isPending}>
            Invite
          </Button>
        </form>
      ) : (
        <p className="text-muted-foreground text-sm">Only owners can invite or remove team members.</p>
      )}
      {err && <p className="text-destructive mt-2 text-sm">{err}</p>}
    </Panel>
  );
}
