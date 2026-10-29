"use client";

import Link from "next/link";
import { useLogout } from "@cn/core/api/auth";
import { siteUrl } from "@cn/core/config/env";
import { useUserStore } from "@cn/core/store/user-store";
import { Seal } from "@cn/ui/layout/logo";

/** Top bar of the staff app: who is signed in, a way to the public site, and sign out. */
export function AdminHeader() {
  const user = useUserStore((s) => s.user);
  const { logout, isLoggingOut } = useLogout("/login");

  return (
    <header className="bg-gov-ink sticky top-0 z-50 flex h-(--nav-h) items-center gap-3 px-4 text-xs text-white">
      <Link href="/" className="flex items-center gap-2 font-semibold">
        <Seal className="size-7" />
        <span>
          Compliance Navigator <span className="text-gov-yellow">Admin</span>
        </span>
      </Link>
      <div className="ml-auto flex items-center gap-4">
        <a href={siteUrl()} target="_blank" rel="noreferrer" className="hover:underline">
          Public site
        </a>
        {user && <span className="hidden text-white/80 sm:inline">{user.fullname || user.email}</span>}
        {user && (
          <button type="button" onClick={() => logout()} disabled={isLoggingOut} className="hover:underline">
            Sign out
          </button>
        )}
      </div>
    </header>
  );
}
