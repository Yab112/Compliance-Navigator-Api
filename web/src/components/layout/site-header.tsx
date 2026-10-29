"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Search01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useUserStore } from "@/store";
import { useLogout } from "@cn/core/api/auth";
import { useAttention, useMyProvider } from "@cn/core/api/providers";
import { mainNav, siteIdentity } from "@cn/core/content/site";
import { cn } from "@cn/core/lib/utils";
import { FlagStripe } from "@cn/ui/layout/flag-stripe";
import { NotificationBell } from "@/components/layout/notification-bell";
import { Logo } from "@cn/ui/layout/logo";
import { adminUrl } from "@cn/core/config/env";

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/roadmap") return pathname === "/roadmap" || /^\/roadmap\/(?!new)/.test(pathname);
  return pathname === href || pathname.startsWith(`${href}/`);
}

function ServiceSearch({ className, onDone }: { className?: string; onDone?: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  return (
    <form
      role="search"
      className={cn("flex", className)}
      onSubmit={(e) => {
        e.preventDefault();
        router.push(q.trim() ? `/services?q=${encodeURIComponent(q.trim())}` : "/services");
        onDone?.();
      }}
    >
      <label htmlFor="header-search" className="sr-only">
        Search government services
      </label>
      <input
        id="header-search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search services · አገልግሎት ይፈልጉ"
        className="border-input bg-background focus:border-primary h-9 min-w-0 flex-1 rounded-l-md border px-3 text-sm outline-none"
      />
      <button
        type="submit"
        aria-label="Search"
        className="bg-primary text-primary-foreground hover:bg-primary/90 flex h-9 w-10 items-center justify-center rounded-r-md"
      >
        <HugeiconsIcon icon={Search01Icon} className="size-4" />
      </button>
    </form>
  );
}


function CountBadge({ n }: { n: number }) {
  if (!n) return null;
  return (
    <span className="bg-gov-yellow text-gov-ink ml-1 inline-flex min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold">
      {n}
    </span>
  );
}

/**
 * "My hires" for clients and "Jobs" for providers. The count is what waits on *you*: pay, confirm,
 * review (client); accept, set a price, start, deliver (provider). Not everything that is open.
 */
function RequestLinks() {
  const signedIn = useUserStore((s) => !!s.user);
  const attention = useAttention(signedIn).data?.payload;
  const provider = useMyProvider(signedIn);
  const isProvider = !!provider.data?.payload.provider;
  const activeHires = attention?.hires ?? 0;
  const newJobs = isProvider ? (attention?.jobs ?? 0) : 0;
  return (
    <>
      {isProvider && (
        <Link href="/me/provider?tab=jobs" className="hover:underline" title="Jobs waiting for you: accept, set a price, start or deliver">
          Jobs · ስራዎች
          <CountBadge n={newJobs} />
        </Link>
      )}
      {isProvider && (
        <Link href="/me/provider?tab=earnings" className="hover:underline" title="Your earnings and withdrawals">
          Earnings · ገቢ
        </Link>
      )}
      <Link href="/account/requests" className="hover:underline" title="Hires waiting for you: pay, confirm or review">
        My hires · የቀጠርኳቸው
        <CountBadge n={activeHires} />
      </Link>
    </>
  );
}

/** `compact` drops the identity row so full-screen pages like the chat keep their room. */
export function SiteHeader({ compact = false }: { compact?: boolean }) {
  const pathname = usePathname();
  const user = useUserStore((s) => s.user);
  const status = useUserStore((s) => s.status);
  const { logout, isLoggingOut } = useLogout();
  const [open, setOpen] = useState(false);
  // Sign-in links come back with the visitor to the page they were on
  const returnTo = pathname.startsWith("/login") || pathname.startsWith("/register") ? "" : `?returnTo=${encodeURIComponent(pathname)}`;

  const account =
    status === "loading" ? (
      <span className="h-3 w-28 animate-pulse rounded bg-white/20" aria-label="Checking sign-in" />
    ) : user ? (
      <>
        {user.role === "admin" && (
          <a href={adminUrl()} className="text-gov-yellow font-semibold hover:underline">
            Admin dashboard
          </a>
        )}
        <NotificationBell />
        <RequestLinks />
        <Link href="/account" className="flex items-center gap-1.5 hover:underline" title="My account">
          <span className="bg-gov-yellow size-1.5 rounded-full" aria-hidden />
          {user.fullname || user.email}
        </Link>
        <button type="button" onClick={() => logout()} disabled={isLoggingOut} className="hover:underline disabled:opacity-60">
          Sign out
        </button>
      </>
    ) : (
      <>
        <Link href={`/login${returnTo}`} className="hover:underline">
          Sign in · ይግቡ
        </Link>
        <Link href={`/register${returnTo}`} className="hover:underline">
          Register · ይመዝገቡ
        </Link>
      </>
    );

  return (
    <>
      <header>
        <FlagStripe />
        {/* Utility bar */}
        <div className="bg-gov-ink text-white/85">
          <div className="mx-auto flex h-8 max-w-6xl items-center justify-between gap-4 px-4 text-[11px]">
            <p className="truncate">
              <span className="hidden sm:inline">{siteIdentity.servingLine} · </span>
              <span>{siteIdentity.servingLineAm}</span>
            </p>
            <div className="hidden shrink-0 items-center gap-4 md:flex">{account}</div>
          </div>
        </div>
        {/* Identity row */}
        {!compact && (
          <div className="border-border bg-card border-b">
            <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-3">
              <Logo size="lg" />
              <ServiceSearch className="hidden w-full max-w-sm md:flex" />
            </div>
          </div>
        )}
      </header>

      {/* Main menu, stays visible while scrolling */}
      <nav aria-label="Main" className="bg-primary sticky top-0 z-50 hidden h-(--nav-h) shadow-sm md:block">
        <ul className="mx-auto flex h-full max-w-6xl items-stretch px-4">
          {mainNav.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex h-full items-center gap-1.5 border-b-[3px] px-3 text-sm whitespace-nowrap text-white/90 lg:px-4",
                    active ? "border-gov-yellow bg-black/15 font-semibold text-white" : "border-transparent hover:bg-black/10 hover:text-white",
                  )}
                >
                  {item.label}
                  <span className="hidden text-xs text-white/60 lg:inline">{item.am}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Mobile: slim sticky bar + collapsible menu */}
      <div className="bg-primary sticky top-0 z-50 h-(--nav-h) md:hidden">
        <div className="flex h-full items-center justify-between px-4 text-sm text-white">
          <span className="font-semibold">
            {mainNav.find((i) => isActive(pathname, i.href))?.label ?? "Menu"}
          </span>
          <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-controls="mobile-menu" className="text-white/90 underline-offset-4 hover:underline">
            {open ? "Close" : "Menu · ምናሌ"}
          </button>
        </div>
        {open && (
          <div id="mobile-menu" className="border-border bg-card absolute inset-x-0 top-full border-b shadow-lg">
            <div className="p-4">
              <ServiceSearch onDone={() => setOpen(false)} />
            </div>
            <ul className="border-border border-t">
              {mainNav.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={() => setOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "border-border flex items-center justify-between border-b border-l-4 px-4 py-3 text-sm",
                        active ? "border-l-primary bg-secondary font-semibold" : "border-l-transparent",
                      )}
                    >
                      {item.label}
                      <span className="text-muted-foreground text-xs">{item.am}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
            <div className="bg-gov-ink flex flex-wrap gap-x-5 gap-y-2 px-4 py-3 text-sm text-white/90" onClick={() => setOpen(false)}>
              {account}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
