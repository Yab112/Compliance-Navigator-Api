"use client";

import { useState } from "react";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Button } from "@cn/ui/button";
import { Pager } from "@cn/ui/pager";
import { AdminPage } from "@/modules/components/admin-page";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { StatusBadge } from "@/modules/shared/status-badge";
import {
  outcomeMessage,
  useCan,
  useRoles,
  useStaffMember,
  useStaffMutations,
  useStaffSessions,
  type LinkResult,
  type StaffMember,
} from "./api";
import { RolePicker } from "./staff-page";
import { AuditTable, Gate, Notice, When } from "./shared";

const SESSION_PAGE = 10;

function LinkBox({ result }: { result: LinkResult }) {
  const [copied, setCopied] = useState(false);
  if (result.email_sent) return <Notice message="Email sent." />;
  return (
    <div className="bg-secondary max-w-md rounded p-2 text-[11px]">
      <p className="font-medium">
        Email isn&apos;t set up on this server, so pass this link on privately (works once, for{" "}
        {result.expires_in_minutes >= 120 ? `${result.expires_in_minutes / 60} hours` : `${result.expires_in_minutes} minutes`}):
      </p>
      <div className="mt-1 flex gap-2">
        <input
          readOnly
          aria-label="One-time link"
          value={result.link ?? ""}
          className="border-border min-w-0 flex-1 border bg-white px-1 font-mono"
          onFocus={(e) => e.target.select()}
        />
        <button
          type="button"
          className="text-primary font-semibold"
          onClick={async () => {
            await navigator.clipboard.writeText(result.link ?? "");
            setCopied(true);
          }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

function RolesEditor({ staff, editable }: { staff: StaffMember; editable: boolean }) {
  const roles = useRoles(0, 200).payload?.items ?? [];
  const { setRoles, isPending } = useStaffMutations();
  const [value, setValue] = useState(staff.roles.map((r) => r.id));
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const changed = [...value].sort().join() !== staff.roles.map((r) => r.id).sort().join();

  if (!editable) {
    return <p className="text-xs">{staff.roles.map((r) => r.name).join(", ") || "No roles"}</p>;
  }
  return (
    <form
      className="space-y-3"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        setMessage(null);
        try {
          setMessage(outcomeMessage(await setRoles(staff.id, value), "Roles changed."));
        } catch (err) {
          setError(getErrorMessage(err, "Could not change roles"));
        }
      }}
    >
      <RolePicker roles={roles} value={value} onChange={setValue} idPrefix="staff-role" />
      <p className="text-muted-foreground text-[11px]">
        Role changes need a second staff member to approve them. Granting or removing Super admin needs another Super admin.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="sm" loading={isPending} disabled={!changed}>
          Save roles
        </Button>
        <Notice message={error} tone="error" />
        <Notice message={message} />
      </div>
    </form>
  );
}

function Sessions({ id }: { id: string }) {
  const [page, setPage] = useState(0);
  const { payload, isLoading } = useStaffSessions(id, page, SESSION_PAGE);
  if (isLoading) return <LoadingState />;
  if (!payload?.items.length) return <EmptyState title="Not signed in anywhere" />;
  return (
    <>
      <ul className="divide-border border-border divide-y border text-xs">
        {payload.items.map((s) => (
          <li key={s.id} className="p-2">
            <p className="truncate">{s.user_agent ?? "Unknown browser"}</p>
            <p className="text-muted-foreground">
              {s.ip ?? "unknown network"} · signed in <When at={s.created_at} />
            </p>
          </li>
        ))}
      </ul>
      <Pager page={page} pageSize={SESSION_PAGE} total={payload.total} onPage={setPage} />
    </>
  );
}

function Detail({ id }: { id: string }) {
  const { can, me } = useCan();
  const { payload, isLoading, error, refetch } = useStaffMember(id);
  const actions = useStaffMutations();
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [link, setLink] = useState<LinkResult | null>(null);

  if (isLoading) return <LoadingState />;
  if (error || !payload) return <ErrorState message={getErrorMessage(error, "Not found")} onRetry={() => refetch()} />;
  const staff = payload.staff;
  const isSelf = staff.id === me?.user.id;
  // Only Super admins change Super admins; nobody changes their own access
  const manage = can("staff.manage") && !isSelf && (!staff.super_admin || !!me?.superAdmin);

  const run = async (fn: () => Promise<unknown>, done: string) => {
    setMessage(null);
    setFailure(null);
    setLink(null);
    try {
      const res = (await fn()) as Parameters<typeof outcomeMessage>[0];
      setMessage(outcomeMessage(res ?? {}, done));
    } catch (e) {
      setFailure(getErrorMessage(e, "That didn't work"));
    }
  };

  return (
    <AdminPage
      title={staff.fullname || staff.email}
      description={`${staff.email}${staff.super_admin ? " · Super admin" : ""}${isSelf ? " · this is you" : ""}`}
    >
      <div className="mb-6 flex flex-wrap items-center gap-3 text-xs">
        <StatusBadge status={staff.status} tone={staff.status === "active" ? "good" : staff.status === "invited" ? "info" : "critical"} />
        <span className="text-muted-foreground">
          Added <When at={staff.created_at} /> by {staff.created_by ?? "unknown"} · last sign-in <When at={staff.last_login_at} />
        </span>
      </div>

      {manage && (
        <section aria-label="Actions" className="mb-6 flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            {staff.status === "invited" && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={actions.isPending}
                  onClick={async () => {
                    setFailure(null);
                    setMessage(null);
                    try {
                      setLink(await actions.sendLink(staff.id, "resend-invite"));
                    } catch (e) {
                      setFailure(getErrorMessage(e, "Could not resend"));
                    }
                  }}
                >
                  Resend invitation
                </Button>
                <Button size="sm" variant="outline" disabled={actions.isPending} onClick={() => run(() => actions.action(staff.id, "revoke-invite"), "Invitation link cancelled.")}>
                  Cancel invitation link
                </Button>
              </>
            )}
            {staff.status === "active" && (
              <Button
                size="sm"
                variant="outline"
                disabled={actions.isPending}
                onClick={async () => {
                  setFailure(null);
                  setMessage(null);
                  try {
                    setLink(await actions.sendLink(staff.id, "reset-password"));
                  } catch (e) {
                    setFailure(getErrorMessage(e, "Could not send"));
                  }
                }}
              >
                Send password reset link
              </Button>
            )}
            <Button size="sm" variant="outline" disabled={actions.isPending || !staff.active_sessions} onClick={() => run(() => actions.action(staff.id, "sign-out"), "Signed out everywhere.")}>
              Sign out everywhere
            </Button>
            {staff.status === "disabled" ? (
              <Button size="sm" variant="secondary" disabled={actions.isPending} onClick={() => run(() => actions.action(staff.id, "enable"), "Enabled.")}>
                Enable
              </Button>
            ) : (
              <Button size="sm" variant="destructive" disabled={actions.isPending} onClick={() => run(() => actions.action(staff.id, "disable"), "Disabled and signed out.")}>
                Disable
              </Button>
            )}
          </div>
          <Notice message={failure} tone="error" />
          <Notice message={message} />
          {link && <LinkBox result={link} />}
        </section>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        <section aria-labelledby="roles-title">
          <h2 id="roles-title" className="mb-3 text-sm font-semibold">
            Roles
          </h2>
          <RolesEditor key={staff.roles.map((r) => r.id).join()} staff={staff} editable={manage} />
          <details className="mt-3 text-xs">
            <summary className="text-primary cursor-pointer">
              {staff.permissions?.length ?? 0} permissions from these roles
            </summary>
            <p className="text-muted-foreground mt-1 font-mono text-[11px] leading-relaxed">{staff.permissions?.join(", ")}</p>
          </details>
        </section>
        <section aria-labelledby="sessions-title">
          <h2 id="sessions-title" className="mb-3 text-sm font-semibold">
            Signed in on ({staff.active_sessions})
          </h2>
          <Sessions id={staff.id} />
        </section>
      </div>

      {staff.recent_actions && (
        <section aria-labelledby="actions-title" className="mt-8">
          <h2 id="actions-title" className="mb-3 text-sm font-semibold">
            Recent actions
          </h2>
          {staff.recent_actions.length ? <AuditTable items={staff.recent_actions} showActor={false} /> : <EmptyState title="Nothing yet" />}
        </section>
      )}
    </AdminPage>
  );
}

export function StaffDetailPage({ id }: { id: string }) {
  return (
    <Gate perm="staff.view">
      <Detail id={id} />
    </Gate>
  );
}
