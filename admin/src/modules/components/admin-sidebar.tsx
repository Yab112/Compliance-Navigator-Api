"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@cn/core/lib/utils";
import { ADMIN_NAV, type AdminNavItem } from "@/modules/components/admin-nav";
import { useCan } from "@/modules/access/api";
import { NAV_PERMISSIONS } from "@/modules/access/nav-permissions";

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  // "/guday" shouldn't light up on "/guday/cases"
  const deeper = ADMIN_NAV.some(
    (n) => n.href !== href && n.href.startsWith(href) && pathname.startsWith(n.href),
  );
  return !deeper && pathname.startsWith(href);
}

export function AdminSidebar() {
  const pathname = usePathname();
  const { can, me } = useCan();
  // Hide what this staff member can't open; the server refuses it anyway
  const visible = (n: AdminNavItem) => {
    const perm = n.perm ?? NAV_PERMISSIONS[n.href];
    return !perm || can(perm);
  };
  const items = ADMIN_NAV.filter(visible);
  const groups = [...new Set(items.map((n) => n.group))];

  return (
    <nav className="flex gap-4 overflow-x-auto p-3 text-xs lg:flex-col lg:gap-5 lg:p-4">
      {groups.map((group) => (
        <div key={group} className="flex shrink-0 gap-1 lg:flex-col">
          <p className="text-muted-foreground hidden px-2 pb-1 text-[10px] font-medium tracking-wider uppercase lg:block">
            {group}
          </p>
          {items.filter((n) => n.group === group).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "hover:bg-muted border-l-[3px] border-transparent px-2 py-1.5 whitespace-nowrap",
                isActive(pathname, item.href) && "border-primary bg-secondary text-primary font-semibold",
              )}
            >
              {item.label}
              {item.href === "/access/approvals" && !!me?.approvalsWaiting && (
                <span className="bg-primary text-primary-foreground ml-1.5 rounded-full px-1.5 text-[10px] tabular-nums">
                  {me.approvalsWaiting}
                  <span className="sr-only"> waiting for you</span>
                </span>
              )}
            </Link>
          ))}
        </div>
      ))}
    </nav>
  );
}
