"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { Textarea } from "@cn/ui/textarea";
import { AdminPage } from "@/modules/components/admin-page";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { outcomeMessage, useCan, usePermissionCatalogue, useRole, useRoleMutations, useRoles, type Role } from "./api";
import { Gate, Notice, RiskBadge, When } from "./shared";

const ROLE_PAGE = 50;

function RolesList() {
  const { can } = useCan();
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(ROLE_PAGE);
  const { payload, isLoading, error, refetch } = useRoles(page, size);
  return (
    <AdminPage
      title="Roles · ሚናዎች"
      description="A role is a named set of permissions. Built-in roles can't be changed; duplicate one to make your own version."
      actions={
        can("roles.manage") ? (
          <Link href="/access/roles/new">
            <Button>New role</Button>
          </Link>
        ) : undefined
      }
    >
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !payload?.items.length ? (
        <EmptyState title="No roles" />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {payload.items.map((r) => (
            <li key={r.id} className="border-border bg-card border p-4 text-xs">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <Link href={`/access/roles/${r.id}`} className="text-primary text-sm font-semibold hover:underline">
                  {r.name}
                </Link>
                <span className="text-muted-foreground">{r.built_in ? "Built-in, read-only" : "Custom"}</span>
              </div>
              <p className="text-muted-foreground mt-1">{r.description}</p>
              <p className="mt-2">
                {r.permissions.length} permissions · {r.members} staff
              </p>
            </li>
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
    </AdminPage>
  );
}

export function RolesPage() {
  return (
    <Gate perm="roles.view">
      <RolesList />
    </Gate>
  );
}

/** Grouped checklist of every permission with its risk; shared by the editor and the read-only view. */
function PermissionChecklist({
  value,
  onChange,
  readOnly,
}: {
  value: string[];
  onChange?: (next: string[]) => void;
  readOnly: boolean;
}) {
  const { payload } = usePermissionCatalogue();
  const { me } = useCan();
  const mine = new Set(me?.permissions ?? []);
  if (!payload) return <LoadingState />;
  const selected = new Set(value);
  return (
    <div className="space-y-4">
      {payload.areas.map((area) => (
        <fieldset key={area.key} className="border-border border p-3">
          <legend className="px-1 text-xs font-semibold">{area.title}</legend>
          <ul className="space-y-2">
            {area.permissions.map((p) => {
              const id = `perm-${p.key}`;
              // Adding a permission you don't hold yourself would be refused by the server
              const blocked = !readOnly && !selected.has(p.key) && !mine.has(p.key);
              return (
                <li key={p.key} className="flex items-start gap-2 text-xs">
                  <input
                    id={id}
                    type="checkbox"
                    className="mt-0.5"
                    checked={selected.has(p.key)}
                    disabled={readOnly || blocked}
                    onChange={(e) =>
                      onChange?.(e.target.checked ? [...value, p.key] : value.filter((v) => v !== p.key))
                    }
                  />
                  <label htmlFor={id} className="min-w-0 flex-1">
                    <span className="font-medium">{p.label}</span> <RiskBadge risk={p.risk} />
                    <span className="text-muted-foreground block">{p.description}</span>
                    <span className="text-muted-foreground block font-mono text-[10px]">{p.key}</span>
                    {blocked && <span className="text-muted-foreground block">You don&apos;t have this permission, so you can&apos;t give it.</span>}
                  </label>
                </li>
              );
            })}
          </ul>
        </fieldset>
      ))}
    </div>
  );
}

function RoleForm({ role, duplicate }: { role: Role | null; duplicate: boolean }) {
  const router = useRouter();
  const { can } = useCan();
  const mutations = useRoleMutations();
  const readOnly = !can("roles.manage") || (!!role?.built_in && !duplicate);
  const [name, setName] = useState(role ? (duplicate ? `${role.name} (copy)` : role.name) : "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [permissions, setPermissions] = useState<string[]>(role?.permissions ?? []);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const isNew = !role || duplicate;

  const save = async () => {
    setError(null);
    setMessage(null);
    try {
      if (isNew) {
        const res = await mutations.create({ name: name.trim(), description, permissions });
        router.push(`/access/roles/${res.role.id}`);
      } else if (role) {
        const res = await mutations.update(role.id, { name: name.trim(), description, permissions });
        setMessage(outcomeMessage(res, "Saved."));
      }
    } catch (e) {
      setError(getErrorMessage(e, "Could not save the role"));
    }
  };

  return (
    <AdminPage
      title={isNew ? "New role" : role!.name}
      description={
        role?.built_in && !duplicate
          ? "Built-in role: read-only. Duplicate it to make a custom version."
          : "Changing a role's permissions needs a second staff member to approve it. Renaming is immediate."
      }
      actions={
        role && !duplicate && can("roles.manage") ? (
          <Link href={`/access/roles/new?from=${role.id}`}>
            <Button variant="outline">Duplicate</Button>
          </Link>
        ) : undefined
      }
    >
      <form
        className="grid gap-6 lg:grid-cols-[minmax(0,18rem)_1fr]"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <div className="space-y-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="role-name">Name</Label>
            <Input id="role-name" required minLength={2} maxLength={60} value={name} readOnly={readOnly} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="role-description">What it is for</Label>
            <Textarea id="role-description" maxLength={300} value={description} readOnly={readOnly} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <p className="text-xs">{permissions.length} permissions selected</p>
          {role && !duplicate && (
            <div className="text-xs">
              <p className="font-medium">Held by {role.staff?.length ?? role.members} staff</p>
              <ul className="text-muted-foreground mt-1 space-y-0.5">
                {role.staff?.map((s) => (
                  <li key={s.id}>
                    <Link href={`/access/staff/${s.id}`} className="hover:underline">
                      {s.fullname || s.email}
                    </Link>{" "}
                    {s.status !== "active" && `(${s.status})`}
                  </li>
                ))}
              </ul>
              <p className="text-muted-foreground mt-2">
                Updated <When at={role.updated_at} />
              </p>
            </div>
          )}
          {!readOnly && (
            <div className="flex flex-wrap gap-2">
              <Button type="submit" loading={mutations.isPending}>
                {isNew ? "Create role" : "Save changes"}
              </Button>
              {role && !duplicate && !role.built_in && (
                <Button
                  type="button"
                  variant="destructive"
                  disabled={mutations.isPending}
                  onClick={async () => {
                    setError(null);
                    try {
                      const res = await mutations.remove(role.id);
                      if (res.deleted) router.push("/access/roles");
                      else setMessage(outcomeMessage(res, "Deleted."));
                    } catch (e) {
                      setError(getErrorMessage(e, "Could not delete"));
                    }
                  }}
                >
                  Delete role
                </Button>
              )}
            </div>
          )}
          <Notice message={error} tone="error" />
          <Notice message={message} />
        </div>
        <PermissionChecklist value={permissions} onChange={setPermissions} readOnly={readOnly} />
      </form>
    </AdminPage>
  );
}

export function RoleEditorPage({ id, from }: { id?: string; from?: string | null }) {
  const source = id ?? from ?? null;
  const { payload, isLoading, error, refetch } = useRole(source);
  let body: React.ReactNode;
  if (source && isLoading) body = <LoadingState />;
  else if (source && (error || !payload)) body = <ErrorState message={getErrorMessage(error, "Role not found")} onRetry={() => refetch()} />;
  else body = <RoleForm key={payload?.role.updated_at ?? "new"} role={payload?.role ?? null} duplicate={!id} />;
  return <Gate perm={id ? "roles.view" : "roles.manage"}>{body}</Gate>;
}

function PermissionsList() {
  const { payload, isLoading, error, refetch } = usePermissionCatalogue();
  return (
    <AdminPage
      title="Permissions · ፈቃዶች"
      description="Every action in this workspace is guarded by one permission. Roles bundle them; this list shows which roles include each one."
    >
      {isLoading ? (
        <LoadingState />
      ) : error || !payload ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : (
        <div className="space-y-6">
          {payload.areas.map((area) => (
            <section key={area.key} aria-labelledby={`area-${area.key}`}>
              <h2 id={`area-${area.key}`} className="mb-2 text-sm font-semibold">
                {area.title}
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-xs">
                  <thead className="text-muted-foreground text-[11px]">
                    <tr>
                      <th className="py-1.5 pr-3 font-medium">Permission</th>
                      <th className="py-1.5 pr-3 font-medium">Risk</th>
                      <th className="py-1.5 font-medium">Roles that include it</th>
                    </tr>
                  </thead>
                  <tbody>
                    {area.permissions.map((p) => (
                      <tr key={p.key} className="border-border border-t align-top">
                        <td className="py-1.5 pr-3">
                          <p className="font-medium">{p.label}</p>
                          <p className="text-muted-foreground">{p.description}</p>
                          <p className="text-muted-foreground font-mono text-[10px]">{p.key}</p>
                        </td>
                        <td className="py-1.5 pr-3">
                          <RiskBadge risk={p.risk} />
                        </td>
                        <td className="py-1.5">{p.roles.join(", ") || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
      )}
    </AdminPage>
  );
}

export function PermissionsPage() {
  return (
    <Gate perm="roles.view">
      <PermissionsList />
    </Gate>
  );
}
