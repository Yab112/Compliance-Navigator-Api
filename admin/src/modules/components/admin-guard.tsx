"use client";

import { siteUrl } from "@cn/core/config/env";
import { Button } from "@cn/ui/button";
import { Spinner } from "@cn/ui/spinner";
import { useRequireAuth } from "@cn/core/hooks/use-require-auth";
import { useUserStore } from "@cn/core/store/user-store";

/** Renders children only for signed-in admins. */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  const user = useUserStore((s) => s.user);
  const gate = useRequireAuth("/login");

  if (gate === "loading") {
    return (
      <div className="flex min-h-[50dvh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (user?.role !== "admin") {
    return (
      <div className="mx-auto max-w-md px-4 py-20 text-center">
        <h1 className="text-lg font-semibold">Admin access required</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Your account ({user?.email}) isn&apos;t an administrator. Ask a Compliance Navigator
          administrator to grant you access.
        </p>
        <a href={siteUrl()} className="mt-6 inline-block">
          <Button variant="outline">Go to the public site</Button>
        </a>
      </div>
    );
  }

  return <>{children}</>;
}
