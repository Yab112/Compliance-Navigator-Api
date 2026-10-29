"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { useUserStore } from "@/store";

/** Renders children only for signed-in admins. */
export function AdminGuard({ children }: { children: React.ReactNode }) {
  const user = useUserStore((s) => s.user);
  const gate = useRequireAuth();

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
          Your account ({user?.email}) isn&apos;t an administrator. Ask a MESOB
          administrator to grant you access.
        </p>
        <Link href="/" className="mt-6 inline-block">
          <Button variant="outline">Back to home</Button>
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
