"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@cn/core/lib/utils";
import { ADMIN_NAV, ADMIN_NAV_GROUPS, type AdminNavItem } from "@/modules/components/admin-nav";
import { useCan } from "@/modules/access/api";
import { NAV_PERMISSIONS } from "@/modules/access/nav-permissions";

const COLLAPSED_KEY = "cn.staff.nav.collapsed";
const ACCOUNT: AdminNavItem = { href: "/account", label: "My account", group: "" };

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  // "/marketplace" shouldn't light up on "/marketplace/hires"
  const deeper = ADMIN_NAV.some(
    (n) => n.href !== href && n.href.startsWith(href) && pathname.startsWith(n.href),
  );
  return !deeper && pathname.startsWith(href);
}

function readCollapsed(): string[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(COLLAPSED_KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function AdminSidebar() {
  const pathname = usePathname();
  const { can, me } = useCan();
  // Sections the person folded away; remembered in this browser only
  // (the guard renders this only in the browser, after sign-in, so reading storage here is safe)
  const [collapsed, setCollapsed] = useState<string[]>(readCollapsed);
  const toggle = (group: string) => {
    const next = collapsed.includes(group) ? collapsed.filter((g) => g !== group) : [...collapsed, group];
    setCollapsed(next);
    try {
      window.localStorage.setItem(COLLAPSED_KEY, JSON.stringify(next));
    } catch {
      // private window or storage blocked: folding still works until reload
    }
  };

  // Hide what this staff member can't open; the server refuses it anyway
  const visible = (n: AdminNavItem) => {
    const perm = n.perm ?? NAV_PERMISSIONS[n.href];
    return !perm || can(perm);
  };
  const items = ADMIN_NAV.filter(visible);
  const groups = ADMIN_NAV_GROUPS.filter((g) => items.some((n) => n.group === g.name));

  const link = (item: AdminNavItem) => (
    <Link
      key={item.href}
      href={item.href}
      aria-current={isActive(pathname, item.href) ? "page" : undefined}
      className={cn(
        "hover:bg-muted flex items-center border-l-[3px] border-transparent px-2 py-1.5 whitespace-nowrap",
        isActive(pathname, item.href) && "border-primary bg-secondary text-primary font-semibold",
      )}
    >
      {item.label}
      {item.href === "/access/approvals" && !!me?.approvalsWaiting && (
        <span className="bg-primary text-primary-foreground ml-auto rounded-full px-1.5 text-[10px] tabular-nums">
          {me.approvalsWaiting}
          <span className="sr-only"> waiting for you</span>
        </span>
      )}
    </Link>
  );

  return (
    <nav aria-label="Staff sections" className="flex h-full flex-col text-xs">
      {/* Phone and tablet: one scrollable strip of every page */}
      <div className="flex gap-1 overflow-x-auto p-3 lg:hidden">{[...items, ACCOUNT].map(link)}</div>

      <div className="hidden min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3 lg:flex">
        {groups.map((group) => {
          const groupItems = items.filter((n) => n.group === group.name);
          const hasActive = groupItems.some((n) => isActive(pathname, n.href));
          // The section holding the open page never folds away
          const open = hasActive || !collapsed.includes(group.name);
          const listId = `nav-${group.name.replace(/\W+/g, "-").toLowerCase()}`;
          return (
            <div key={group.name}>
              <button
                type="button"
                onClick={() => toggle(group.name)}
                disabled={hasActive}
                aria-expanded={open}
                aria-controls={listId}
                title={group.hint}
                className="text-muted-foreground hover:text-foreground flex w-full items-center justify-between px-2 pb-1 text-[10px] font-medium tracking-wider uppercase disabled:cursor-default disabled:hover:text-current"
              >
                {group.name}
                {!hasActive && <span aria-hidden>{open ? "−" : "+"}</span>}
              </button>
              {open && (
                <div id={listId} className="flex flex-col">
                  {groupItems.map(link)}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="border-border hidden border-t p-3 lg:block">
        {link(ACCOUNT)}
      </div>
    </nav>
  );
}
