"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useUserStore } from "@/store";
import { useLogout } from "@/api/auth";
import { cn } from "@/lib/utils";
import { Logo } from "./logo";

const nav = [
  { href: "/", label: "Home" },
  { href: "/roadmap/new", label: "Find my path" },
  { href: "/chat", label: "Chat" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/roadmap", label: "My path" },
  { href: "/about", label: "About" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const { user } = useUserStore();
  const { logout, isLoggingOut } = useLogout();

  return (
    <header className="border-border bg-background/95 sticky top-0 z-50 border-b backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
        <Logo showName size="sm" />

        <nav className="flex items-center gap-1">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded-none px-3 py-1.5 text-xs",
                pathname === item.href && "bg-muted font-medium",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {user ? (
            <>
              <span className="text-muted-foreground hidden text-xs md:inline">
                {user.fullname}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => logout()}
                loading={isLoggingOut}
              >
                Sign out
              </Button>
            </>
          ) : (
            <Link href="/login">
              <Button size="sm">Sign in</Button>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
