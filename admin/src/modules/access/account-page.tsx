"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { getErrorMessage } from "@cn/core/lib/errors";
import { staffLogout } from "@cn/core/lib/staff-session";
import { PasswordInput, passwordIsValid } from "@cn/ui/auth/password-input";
import { Button } from "@cn/ui/button";
import { Label } from "@cn/ui/label";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { AdminPage } from "@/modules/components/admin-page";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { useMyAccountMutations, useMyActivity, useMySessions, useStaffMe } from "./api";
import { AuditTable, Notice, When } from "./shared";

const SMALL_PAGE = 10;

export function ChangePasswordForm() {
  const { changePassword, isPending } = useMyAccountMutations();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  return (
    <form
      className="flex max-w-sm flex-col gap-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        setDone(null);
        if (!passwordIsValid(next)) return setError("The new password doesn't meet the rules.");
        if (next !== confirm) return setError("The two new passwords don't match.");
        try {
          const res = await changePassword(current, next);
          setCurrent("");
          setNext("");
          setConfirm("");
          setDone(`Password changed. ${res.otherSessionsSignedOut} other session(s) were signed out.`);
        } catch (err) {
          setError(getErrorMessage(err, "Could not change the password"));
        }
      }}
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor="current-password">Current password</Label>
        <PasswordInput id="current-password" value={current} onChange={setCurrent} autoComplete="current-password" locked />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="new-password">New password</Label>
        <PasswordInput id="new-password" value={next} onChange={setNext} autoComplete="new-password" showRules locked />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="confirm-password">Type the new password again</Label>
        <PasswordInput id="confirm-password" value={confirm} onChange={setConfirm} autoComplete="new-password" locked />
      </div>
      <Notice message={error} tone="error" />
      <Notice message={done} />
      <Button type="submit" loading={isPending} className="self-start">
        Change password
      </Button>
    </form>
  );
}

function MySessions() {
  const [page, setPage] = useUrlPage("sessions_page");
  const [size, setSize] = useUrlPageSize(SMALL_PAGE, "sessions_page");
  const { payload, isLoading, error, refetch } = useMySessions(page, size);
  const { endSession, isPending } = useMyAccountMutations();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />;
  return (
    <>
      {!payload?.items.length ? (
        <EmptyState title="No active sessions" />
      ) : (
        <ul className="divide-border border-border divide-y border text-xs">
          {payload.items.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
              <div className="min-w-0">
                <p className="truncate font-medium">
                  {s.user_agent ?? "Unknown browser"}
                  {s.current && <span className="text-primary"> (this browser)</span>}
                </p>
                <p className="text-muted-foreground">
                  {s.ip ?? "unknown network"} · signed in <When at={s.created_at} /> · ends <When at={s.expires_at} />
                </p>
              </div>
              {!s.current && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isPending}
                  onClick={async () => {
                    try {
                      await endSession(s.id);
                      setMessage("That session was signed out.");
                    } catch (e) {
                      setMessage(getErrorMessage(e, "Could not sign it out"));
                    }
                  }}
                >
                  Sign out
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={async () => {
            await staffLogout(true);
            queryClient.clear();
            router.push("/login");
          }}
        >
          Sign out everywhere
        </Button>
        <Notice message={message} />
      </div>
    </>
  );
}

function MyActivity() {
  const [page, setPage] = useUrlPage("activity_page");
  const [size, setSize] = useUrlPageSize(SMALL_PAGE, "activity_page");
  const { payload, isLoading, error, refetch } = useMyActivity(page, size);
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />;
  return (
    <>
      {!payload?.items.length ? <EmptyState title="Nothing yet" /> : <AuditTable items={payload.items} showActor={false} />}
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
    </>
  );
}

export function AccountPage() {
  const { payload } = useStaffMe();
  return (
    <AdminPage title="My account · የእኔ መለያ" description="Your staff sign-in, password, sessions and what you did recently.">
      <div className="grid gap-8 lg:grid-cols-2">
        <section aria-labelledby="who" className="space-y-2 text-xs">
          <h2 id="who" className="text-sm font-semibold">
            You
          </h2>
          <p>
            <span className="font-medium">{payload?.user.fullname || "No name"}</span> · {payload?.user.email}
          </p>
          <p className="text-muted-foreground">
            Roles: {payload?.roles.map((r) => r.name).join(", ") || "none"} ({payload?.permissions.length ?? 0} permissions)
          </p>
          <p className="text-muted-foreground">Ask a Super admin to change your roles. Nobody can change their own.</p>
        </section>
        <section aria-labelledby="pw">
          <h2 id="pw" className="mb-3 text-sm font-semibold">
            Change password
          </h2>
          <ChangePasswordForm />
        </section>
      </div>
      <section aria-labelledby="sessions" className="mt-8">
        <h2 id="sessions" className="mb-3 text-sm font-semibold">
          Where you are signed in
        </h2>
        <MySessions />
      </section>
      <section aria-labelledby="activity" className="mt-8">
        <h2 id="activity" className="mb-3 text-sm font-semibold">
          Your recent activity
        </h2>
        <MyActivity />
      </section>
    </AdminPage>
  );
}
