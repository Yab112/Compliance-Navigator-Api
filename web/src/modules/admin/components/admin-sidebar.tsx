"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { ADMIN_NAV } from "./admin-nav";

function isActive(pathname: string, href: string) {
  if (href === "/admin") return pathname === "/admin";
  // "/admin/guday" shouldn't light up on "/admin/guday/cases"
  const deeper = ADMIN_NAV.some(
    (n) => n.href !== href && n.href.startsWith(href) && pathname.startsWith(n.href),
  );
  return !deeper && pathname.startsWith(href);
}

export function AdminSidebar() {
  const pathname = usePathname();
  const groups = [...new Set(ADMIN_NAV.map((n) => n.group))];

  return (
    <nav className="flex gap-4 overflow-x-auto p-3 text-xs lg:flex-col lg:gap-5 lg:p-4">
      {groups.map((group) => (
        <div key={group} className="flex shrink-0 gap-1 lg:flex-col">
          <p className="text-muted-foreground hidden px-2 pb-1 text-[10px] font-medium tracking-wider uppercase lg:block">
            {group}
          </p>
          {ADMIN_NAV.filter((n) => n.group === group).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "hover:bg-muted border-l-[3px] border-transparent px-2 py-1.5 whitespace-nowrap",
                isActive(pathname, item.href) && "border-primary bg-secondary text-primary font-semibold",
              )}
            >
              {item.label}
            </Link>
          ))}
        </div>
      ))}
    </nav>
  );
}
