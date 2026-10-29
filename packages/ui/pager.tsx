"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect } from "react";
import { Button } from "./button";
import { cn } from "@cn/core/lib/utils";

/**
 * Previous · Page X of Y · N items · Next. Renders nothing when everything fits on one page.
 * `page` is 0-based. When the list shrinks (an item was approved or removed) and `page` is past the
 * end, it moves back to the last page that still has items. Keep it mounted when the page is empty
 * so that can happen.
 */
export function Pager({
  page,
  pageSize,
  total,
  onPage,
  className,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  className?: string;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  useEffect(() => {
    if (total > 0 && page > pages - 1) onPage(pages - 1);
  }, [total, page, pages, onPage]);
  if (total <= pageSize) return null;
  const current = Math.min(page, pages - 1);
  return (
    <nav
      aria-label="Pagination"
      className={cn("mt-4 flex items-center justify-between gap-2 text-xs", className)}
    >
      <Button
        variant="outline"
        size="sm"
        disabled={current <= 0}
        onClick={() => onPage(current - 1)}
        aria-label="Previous page"
      >
        Previous
      </Button>
      <span className="text-muted-foreground text-center" aria-live="polite">
        Page {current + 1} of {pages}
        <span className="hidden sm:inline">
          {" "}
          · {total.toLocaleString("en")} item{total === 1 ? "" : "s"}
        </span>
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={current + 1 >= pages}
        onClick={() => onPage(current + 1)}
        aria-label="Next page"
      >
        Next
      </Button>
    </nav>
  );
}

/**
 * 0-based page number kept in a URL search param (page 0 removes the param).
 * Components using this need a <Suspense> boundary because of useSearchParams.
 */
export function useUrlPage(param = "page"): [number, (page: number) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const page = Math.max(0, Math.floor(Number(params.get(param) ?? 0)) || 0);
  const setPage = useCallback(
    (next: number) => {
      const sp = new URLSearchParams(window.location.search);
      if (next > 0) sp.set(param, String(next));
      else sp.delete(param);
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, param],
  );
  return [page, setPage];
}
