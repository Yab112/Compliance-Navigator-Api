"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAdminUsers, useAuthEvents, useAuthSummary, useUpdateUser, useUserSecurityActions } from "@/api/admin";
import { getErrorMessage } from "@/lib/errors";
import { useUserStore } from "@/store";
import { AdminPage } from "@/modules/admin/components/admin-page";
import { formatDate, timeAgo } from "@/modules/admin/shared/format";
import { NativeSelect } from "@/modules/admin/shared/native-select";
import { EmptyState, ErrorState, LoadingState } from "@/modules/admin/shared/states";
import { StatusBadge } from "@/modules/admin/shared/status-badge";
import { StatTile } from "@/modules/admin/shared/stat-tile";
import type { AdminUser } from "@/types/admin";

const PAGE_SIZE = 25;
const ROLES = ["user", "agent", "admin"] as const;

function UserRow({ user, isSelf }: { user: AdminUser; isSelf: boolean }) {
  const { updateUser, isPending } = useUpdateUser();
  const security = useUserSecurityActions();
  const [error, setError] = useState<string | null>(null);
  const [resetLink, setResetLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const run = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(getErrorMessage(e, "Action failed"));
    }
  };

  const patch = async (body: { role?: string; is_active?: boolean }) => {
    setError(null);
    try {
      await updateUser(user.id, body);
    } catch (e) {
      setError(getErrorMessage(e, "Couldn't update the user"));
    }
  };

  return (
    <tr className="border-border border-t align-top">
      <td className="py-2 pr-3">
        <p className="font-medium">{user.fullname || "-"}{isSelf && <span className="text-muted-foreground"> (you)</span>}</p>
        <p className="text-muted-foreground text-[11px]">{user.email}</p>
        {error && <p className="text-destructive text-[11px]">{error}</p>}
        {resetLink && (
          <div className="bg-secondary mt-2 max-w-sm rounded p-2 text-[11px]">
            <p className="font-medium">Reset link (valid 1 hour, single use): give it to the user privately:</p>
            <div className="mt-1 flex gap-2">
              <input readOnly value={resetLink} className="border-border min-w-0 flex-1 border bg-white px-1 font-mono" onFocus={(e) => e.target.select()} />
              <button
                type="button"
                className="text-primary font-semibold"
                onClick={async () => {
                  await navigator.clipboard.writeText(resetLink);
                  setCopied(true);
                }}
              >
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        )}
      </td>
      <td className="py-2 pr-3">
        <NativeSelect
          aria-label={`Role for ${user.email}`}
          value={user.role}
          disabled={isPending}
          onChange={(e) => patch({ role: e.target.value })}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </NativeSelect>
      </td>
      <td className="py-2 pr-3">
        <StatusBadge status={user.is_active ? "active" : "deactivated"} tone={user.is_active ? "good" : "critical"} />
      </td>
      <td className="py-2 pr-3 whitespace-nowrap">
        {user.active_sessions ? (
          <span className="text-primary font-medium">● {user.active_sessions} device{user.active_sessions > 1 ? "s" : ""}</span>
        ) : (
          <span className="text-muted-foreground">Signed out</span>
        )}
        <p className="text-muted-foreground text-[11px]">last login {timeAgo(user.last_login_at)}</p>
      </td>
      <td className="text-muted-foreground py-2 pr-3 whitespace-nowrap">{formatDate(user.created_at)}</td>
      <td className="py-2 text-right">
        <div className="flex flex-wrap justify-end gap-1.5">
          {!isSelf && (
            <>
              <Button
                size="sm"
                variant="outline"
                disabled={security.isPending}
                onClick={() =>
                  run(async () => {
                    const res = await security.issueResetLink(user.id);
                    setCopied(false);
                    setResetLink(res.link ?? null);
                  })
                }
              >
                Reset link
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={security.isPending || !user.active_sessions}
                onClick={() => run(() => security.revokeSessions(user.id))}
              >
                Sign out
              </Button>
            </>
          )}
          <Button size="sm" variant={user.is_active ? "outline" : "secondary"} disabled={isPending || isSelf} onClick={() => patch({ is_active: !user.is_active })}>
            {user.is_active ? "Deactivate" : "Activate"}
          </Button>
        </div>
      </td>
    </tr>
  );
}

export function UsersPage() {
  const me = useUserStore((s) => s.user);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(0);

  // Debounce the search box
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(search.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const { payload, isLoading, error, refetch } = useAdminUsers(q, role, page, PAGE_SIZE);
  const total = payload?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <AdminPage
      title="Users & roles"
      description="Everyone with an account. Admins manage this dashboard; agents are approved Guday Geday (role is set automatically on approval)."
    >
      <SecuritySummary />
      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or email" aria-label="Search users" className="sm:max-w-xs" />
        <NativeSelect value={role} onChange={(e) => { setRole(e.target.value); setPage(0); }} aria-label="Filter by role">
          <option value="">All roles</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </NativeSelect>
      </div>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !payload?.items.length ? (
        <EmptyState title="No users match" />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-xs">
              <thead className="text-muted-foreground text-[11px]">
                <tr>
                  <th className="py-2 pr-3 font-medium">User</th>
                  <th className="py-2 pr-3 font-medium">Role</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Sign-in</th>
                  <th className="py-2 pr-3 font-medium">Joined</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {payload.items.map((u) => (
                  <UserRow key={u.id} user={u} isSelf={u.id === me?.id} />
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-muted-foreground mt-4 flex items-center justify-between text-xs">
            <span>
              {total.toLocaleString("en")} user{total === 1 ? "" : "s"} · page {page + 1} of {pages}
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button size="sm" variant="outline" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </div>
        </>
      )}
      <SecurityActivity />
    </AdminPage>
  );
}

const EVENT_TONE: Record<string, string> = {
  login_failed: "text-amber-700",
  login_blocked: "text-destructive",
  refresh_reuse: "text-destructive",
  password_change_failed: "text-amber-700",
};

function SecuritySummary() {
  const { payload } = useAuthSummary();
  if (!payload) return null;
  return (
    <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile label="Signed in now" value={payload.signed_in_users} hint={`${payload.active_sessions} active sessions`} />
      <StatTile label="New accounts (7 days)" value={payload.registrations_7d} />
      <StatTile
        label="Failed sign-ins (24 h)"
        value={payload.failed_logins_24h}
        hint={`${payload.blocked_24h} blocked by rate limit`}
        tone={payload.blocked_24h ? "attention" : "default"}
      />
      <StatTile
        label="Stolen-session alerts (7 days)"
        value={payload.token_reuse_7d}
        hint="Refresh token reused after rotation"
        tone={payload.token_reuse_7d ? "attention" : "default"}
      />
    </div>
  );
}

function SecurityActivity() {
  const { payload } = useAuthEvents();
  if (!payload?.events.length) return null;
  return (
    <section className="mt-8">
      <h2 className="mb-2 text-sm font-semibold">Recent sign-in activity</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-xs">
          <thead className="text-muted-foreground text-[11px]">
            <tr>
              <th className="py-1.5 pr-3 font-medium">When</th>
              <th className="py-1.5 pr-3 font-medium">Event</th>
              <th className="py-1.5 pr-3 font-medium">Account</th>
              <th className="py-1.5 pr-3 font-medium">IP</th>
              <th className="py-1.5 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {payload.events.map((e) => (
              <tr key={e.id} className="border-border border-t">
                <td className="text-muted-foreground py-1.5 pr-3 whitespace-nowrap">{timeAgo(e.created_at)}</td>
                <td className={`py-1.5 pr-3 font-medium ${EVENT_TONE[e.event] ?? ""}`}>{e.event.replace(/_/g, " ")}</td>
                <td className="py-1.5 pr-3">{e.email ?? "-"}</td>
                <td className="text-muted-foreground py-1.5 pr-3 font-mono">{e.ip ?? "-"}</td>
                <td className="text-muted-foreground py-1.5">{e.detail ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
