"use client";

import { Spinner } from "@cn/ui/spinner";
import { useRequireAuth } from "@cn/core/hooks/use-require-auth";
import { getErrorMessage } from "@cn/core/lib/errors";
import { useStaffMe } from "@/modules/access/api";
import { ChangePasswordForm } from "@/modules/access/account-page";
import { ErrorState } from "@/modules/shared/states";

/** Renders children only for signed-in staff (the separate staff realm). */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  const gate = useRequireAuth("/login");
  const me = useStaffMe();

  if (gate === "loading" || me.isLoading) {
    return (
      <div className="flex min-h-[50dvh] items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (me.error || !me.payload) {
    return (
      <div className="mx-auto max-w-md px-4 py-20">
        <ErrorState error={me.error} message={getErrorMessage(me.error, "Could not load your staff account")} onRetry={() => me.refetch()} />
      </div>
    );
  }
  if (me.payload.user.mustChangePassword) {
    return (
      <div className="mx-auto max-w-md px-4 py-12">
        <h1 className="text-lg font-semibold">Choose a new password</h1>
        <p className="text-muted-foreground mt-1 mb-6 text-xs">You need to change your password before you continue.</p>
        <ChangePasswordForm />
      </div>
    );
  }

  return <>{children}</>;
}
