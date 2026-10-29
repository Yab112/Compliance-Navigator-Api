"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { staffLogout } from "@cn/core/lib/staff-session";
import { useUserStore } from "@cn/core/store/user-store";
import { Seal } from "@cn/ui/layout/logo";

/** Top bar of the staff app: who is signed in, their account, and sign out. */
export function AdminHeader() {
  const user = useUserStore((s) => s.user);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isLoggingOut, setLoggingOut] = useState(false);

  const logout = async () => {
    setLoggingOut(true);
    await staffLogout();
    queryClient.clear();
    setLoggingOut(false);
    router.push("/login");
  };

  return (
    <header className="bg-gov-ink sticky top-0 z-50 flex h-(--nav-h) items-center gap-3 px-4 text-xs text-white">
      <Link href="/" className="flex items-center gap-2 font-semibold">
        <Seal className="size-7" />
        <span>
          Compliance Navigator <span className="text-gov-yellow">Staff</span>
        </span>
      </Link>
      <div className="ml-auto flex items-center gap-4">
        {user && (
          <Link href="/account" className="hidden max-w-48 truncate text-white/80 hover:underline sm:inline">
            {user.fullname || user.email}
          </Link>
        )}
        {user && (
          <button type="button" onClick={logout} disabled={isLoggingOut} className="hover:underline">
            Sign out
          </button>
        )}
      </div>
    </header>
  );
}
