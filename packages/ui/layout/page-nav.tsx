"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useSyncExternalStore } from "react";
import { cn } from "@cn/core/lib/utils";
import { findRoute, labelFor, navSnapshot, parentOf, recordVisit, rememberLabel, subscribeNav, trailFor } from "@cn/core/lib/navigation";

/** Records each in-app navigation so "Back" knows where the person came from. Mounted once in AppShell. */
export function NavTracker() {
  const pathname = usePathname();
  const params = useSearchParams();
  const query = params.toString();
  useEffect(() => {
    recordVisit(query ? `${pathname}?${query}` : pathname);
  }, [pathname, query]);
  return null;
}

/**
 * "‹ Back to My account" and the breadcrumb trail, the same on every page.
 * Back returns to the page the person actually came from in this tab; without one (opened from a
 * link or a new tab) it goes to the page's parent.
 */
export function PageNav({ label, className, tone = "default" }: { label: string; className?: string; tone?: "default" | "onDark" }) {
  const pathname = usePathname();
  const router = useRouter();
  // Session history lives in the browser; the server (and first paint) render the parent instead
  const snapshot = useSyncExternalStore(subscribeNav, navSnapshot, () => "");
  const state = useMemo(() => {
    if (!snapshot) return { labels: {} as Record<string, string>, previous: null as string | null };
    const [stackJson, labelsJson] = snapshot.split("\u0000");
    const stack: string[] = JSON.parse(stackJson || "[]");
    const here = stack.length ? stack[stack.length - 1].split("?")[0] : null;
    return {
      labels: JSON.parse(labelsJson || "{}") as Record<string, string>,
      previous: here === pathname && stack.length >= 2 ? stack[stack.length - 2] : null,
    };
  }, [snapshot, pathname]);

  // Fixed pages always use their one name from the map, so a page is called the same everywhere;
  // pages about one thing (a provider, a ticket, a saved path) use their own title
  const route = findRoute(pathname);
  const isDynamic = !route || route.def.pattern.includes("[") || !route.def.label;
  const current = isDynamic ? label : route!.def.label!;

  useEffect(() => {
    if (isDynamic) rememberLabel(pathname, label);
  }, [pathname, label, isDynamic]);

  if (pathname === "/") return null;
  const trail = trailFor(pathname, state.labels);
  const parent = parentOf(pathname);
  const backTo = state.previous ?? parent;
  const backLabel = labelFor(backTo.split("?")[0], state.labels);
  const muted = tone === "onDark" ? "text-white/70 hover:text-white" : "text-muted-foreground hover:text-primary";

  return (
    <div className={cn("mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs", className)}>
      {state.previous ? (
        <button type="button" onClick={() => router.back()} className={cn("font-semibold", tone === "onDark" ? "text-white" : "text-primary", "hover:underline")}>
          ‹ Back to {backLabel}
        </button>
      ) : (
        <Link href={backTo} className={cn("font-semibold", tone === "onDark" ? "text-white" : "text-primary", "hover:underline")}>
          ‹ Back to {backLabel}
        </Link>
      )}
      <nav aria-label="Breadcrumb" className={cn("min-w-0", tone === "onDark" ? "text-white/70" : "text-muted-foreground")}>
        <ol className="flex flex-wrap items-center gap-1">
          {trail.map((c) => (
            <li key={c.href} className="flex items-center gap-1">
              <Link href={c.href} className={cn("hover:underline", muted)}>{c.label}</Link>
              <span aria-hidden>›</span>
            </li>
          ))}
          <li aria-current="page" className={cn("truncate", tone === "onDark" ? "text-white" : "text-foreground")}>{current}</li>
        </ol>
      </nav>
    </div>
  );
}

/** PageNav in a page-width row, for pages that don't use PageShell (profiles, hero pages). */
export function PageNavBar({ label, className, tone }: { label: string; className?: string; tone?: "default" | "onDark" }) {
  return (
    <div className={cn("mx-auto max-w-6xl px-4 pt-4", className)}>
      <PageNav label={label} tone={tone} className="mb-0" />
    </div>
  );
}
