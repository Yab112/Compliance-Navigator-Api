"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@cn/core/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@cn/ui/dropdown-menu";
import { ADMIN_NAV, ADMIN_NAV_GROUPS, type AdminNavItem } from "@/modules/components/admin-nav";
import { useCan } from "@/modules/access/api";
import { NAV_PERMISSIONS } from "@/modules/access/nav-permissions";

// Pages people open every day sit in the bar itself; every other section is a menu
const DIRECT_GROUP = "Daily work";

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  // "/marketplace" shouldn't light up on "/marketplace/hires"
  const deeper = ADMIN_NAV.some(
    (n) => n.href !== href && n.href.startsWith(href) && pathname.startsWith(n.href),
  );
  return !deeper && pathname.startsWith(href);
}

const tab = (active: boolean) =>
  cn(
    "flex h-full shrink-0 items-center gap-1 border-b-2 px-3 text-xs whitespace-nowrap outline-none",
    "hover:text-foreground focus-visible:bg-muted",
    active ? "border-primary text-primary font-semibold" : "text-muted-foreground border-transparent",
  );

/** The staff app's navigation: one bar under the header, full width for the page below. */
export function AdminTopNav() {
  const pathname = usePathname();
  const { can, me } = useCan();

  // Hide what this staff member can't open; the server refuses it anyway
  const visible = (n: AdminNavItem) => {
    const perm = n.perm ?? NAV_PERMISSIONS[n.href];
    return !perm || can(perm);
  };
  const items = ADMIN_NAV.filter(visible);
  const direct = items.filter((n) => n.group === DIRECT_GROUP);
  const groups = ADMIN_NAV_GROUPS.filter((g) => g.name !== DIRECT_GROUP && items.some((n) => n.group === g.name));
  const waiting = me?.approvalsWaiting ?? 0;

  return (
    <nav aria-label="Staff sections" className="border-border bg-card sticky top-(--nav-h) z-40 border-b">
      <div className="flex h-11 items-stretch overflow-x-auto px-2 sm:px-4">
        {direct.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={tab(active)}>
              {item.label}
              {item.href === "/access/approvals" && waiting > 0 && (
                <span className="bg-primary text-primary-foreground rounded-full px-1.5 text-[10px] tabular-nums">
                  {waiting}
                  <span className="sr-only"> waiting for you</span>
                </span>
              )}
            </Link>
          );
        })}
        <span className="bg-border mx-2 my-3 w-px shrink-0" aria-hidden />
        {groups.map((group) => {
          const groupItems = items.filter((n) => n.group === group.name);
          const active = groupItems.some((n) => isActive(pathname, n.href));
          return (
            <DropdownMenu key={group.name}>
              <DropdownMenuTrigger className={tab(active)}>
                {group.name}
                <span className="text-[10px]" aria-hidden>▾</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="ring-border w-64 shadow-lg">
                <DropdownMenuGroup>
                  <DropdownMenuLabel>{group.hint}</DropdownMenuLabel>
                  {groupItems.map((item) => (
                    <DropdownMenuItem
                      key={item.href}
                      render={<Link href={item.href} />}
                      className={cn(isActive(pathname, item.href) && "text-primary font-semibold")}
                    >
                      {item.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          );
        })}
      </div>
    </nav>
  );
}
