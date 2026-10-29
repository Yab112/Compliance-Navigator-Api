"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { AdminPage } from "@/modules/components/admin-page";
import { NativeSelect } from "@/modules/shared/native-select";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { StatusBadge } from "@/modules/shared/status-badge";
import { PAGE_SIZE, outcomeMessage, useCan, useRoles, useStaffList, useStaffMutations, type Role } from "./api";
import { Gate, Notice, When } from "./shared";

const STATUS_TONE = { active: "good", invited: "info", disabled: "critical" } as const;

export function RolePicker({
  roles,
  value,
  onChange,
  idPrefix,
}: {
  roles: Role[];
  value: string[];
  onChange: (ids: string[]) => void;
  idPrefix: string;
}) {
  const { me } = useCan();
  const mine = new Set(me?.permissions ?? []);
  return (
    <fieldset className="space-y-1.5">
      <legend className="mb-1 text-xs font-medium">Roles</legend>
      {roles.map((r) => {
        // You can only hand out a role whose permissions you hold yourself
        const allowed = r.permissions.every((p) => mine.has(p));
        const id = `${idPrefix}-${r.id}`;
        return (
          <div key={r.id} className="flex items-start gap-2 text-xs">
            <input
              id={id}
              type="checkbox"
              className="mt-0.5"
              checked={value.includes(r.id)}
              disabled={!allowed && !value.includes(r.id)}
              onChange={(e) => onChange(e.target.checked ? [...value, r.id] : value.filter((v) => v !== r.id))}
            />
            <label htmlFor={id}>
              <span className="font-medium">{r.name}</span>
              {r.built_in && <span className="text-muted-foreground"> (built-in)</span>}
              <span className="text-muted-foreground block">{r.description || `${r.permissions.length} permissions`}</span>
              {!allowed && <span className="text-muted-foreground block">You can&apos;t give this role: it has permissions you don&apos;t have.</span>}
            </label>
          </div>
        );
      })}
    </fieldset>
  );
}

function InviteForm({ onDone }: { onDone: () => void }) {
  const roles = useRoles(0, 200).payload?.items ?? [];
  const { invite, isPending } = useStaffMutations();
  const [email, setEmail] = useState("");
  const [fullname, setFullname] = useState("");
  const [roleIds, setRoleIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  return (
    <form
      className="border-border bg-card mb-6 grid gap-4 border p-4 sm:grid-cols-2"
      aria-labelledby="invite-title"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        setMessage(null);
        if (!roleIds.length) return setError("Choose at least one role.");
        try {
          const res = await invite({ email: email.trim(), fullname: fullname.trim(), role_ids: roleIds });
          setMessage(
            outcomeMessage(
              res,
              "Invitation sent. They get an email with their sign-in email and a link to choose a password (valid 48 hours).",
            ),
          );
          setEmail("");
          setFullname("");
          setRoleIds([]);
        } catch (err) {
          setError(getErrorMessage(err, "Could not invite"));
        }
      }}
    >
      <h2 id="invite-title" className="text-sm font-semibold sm:col-span-2">
        Invite a staff member
      </h2>
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-email">Work email</Label>
          <Input id="invite-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-name">Full name</Label>
          <Input id="invite-name" value={fullname} onChange={(e) => setFullname(e.target.value)} maxLength={120} />
        </div>
        <p className="text-muted-foreground text-[11px]">
          Inviting someone needs a second staff member to approve it (Approvals). They then get an email with a one-time
          link to set their password.
        </p>
      </div>
      <RolePicker roles={roles} value={roleIds} onChange={setRoleIds} idPrefix="invite-role" />
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <Button type="submit" loading={isPending}>
          Send invitation
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Close
        </Button>
        <Notice message={error} tone="error" />
        <Notice message={message} />
      </div>
    </form>
  );
}

function StaffList() {
  const { can } = useCan();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [roleId, setRoleId] = useState("");
  const [page, setPage] = useUrlPage();
  const [inviting, setInviting] = useState(false);
  const roles = useRoles(0, 200).payload?.items ?? [];

  useEffect(() => {
    const t = setTimeout(() => {
      if (search.trim() !== q) {
        setQ(search.trim());
        setPage(0);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [search, q, setPage]);

  const { payload, isLoading, error, refetch } = useStaffList({ q, status, role_id: roleId, page });

  return (
    <AdminPage
      title="Staff · ሰራተኞች"
      description="People who can sign in to this workspace. What each person can do comes from their roles. Staff accounts are separate from public site accounts."
      actions={
        can("staff.manage") && !inviting ? <Button onClick={() => setInviting(true)}>Invite staff</Button> : undefined
      }
    >
      {inviting && <InviteForm onDone={() => setInviting(false)} />}
      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or email" aria-label="Search staff" className="sm:max-w-xs" />
        <NativeSelect value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }} aria-label="Filter by status">
          <option value="">Any status</option>
          <option value="active">Active</option>
          <option value="invited">Invited</option>
          <option value="disabled">Disabled</option>
        </NativeSelect>
        <NativeSelect value={roleId} onChange={(e) => { setRoleId(e.target.value); setPage(0); }} aria-label="Filter by role">
          <option value="">Any role</option>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </NativeSelect>
      </div>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !payload?.items.length ? (
        <EmptyState title="No staff match" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="py-2 pr-3 font-medium">Person</th>
                <th className="py-2 pr-3 font-medium">Roles</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Last sign-in</th>
                <th className="py-2 font-medium">Added</th>
              </tr>
            </thead>
            <tbody>
              {payload.items.map((s) => (
                <tr key={s.id} className="border-border border-t align-top">
                  <td className="py-2 pr-3">
                    <Link href={`/access/staff/${s.id}`} className="text-primary font-medium hover:underline">
                      {s.fullname || s.email}
                    </Link>
                    <p className="text-muted-foreground text-[11px]">{s.email}</p>
                  </td>
                  <td className="py-2 pr-3">{s.roles.map((r) => r.name).join(", ") || "-"}</td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={s.status} tone={STATUS_TONE[s.status]} />
                    {s.invite?.expired && <p className="text-muted-foreground text-[11px]">invitation expired</p>}
                  </td>
                  <td className="py-2 pr-3">
                    <When at={s.last_login_at} />
                    {s.active_sessions > 0 && <p className="text-primary text-[11px]">● signed in on {s.active_sessions}</p>}
                  </td>
                  <td className="text-muted-foreground py-2">
                    <When at={s.created_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={page} pageSize={PAGE_SIZE} total={payload?.total ?? 0} onPage={setPage} />
    </AdminPage>
  );
}

export function StaffPage() {
  return (
    <Gate perm="staff.view">
      <StaffList />
    </Gate>
  );
}
