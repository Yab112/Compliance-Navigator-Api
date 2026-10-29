"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useId } from "react";
import { Button } from "./button";
import { cn } from "@cn/core/lib/utils";

export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

/** 1-based page numbers to show, with null for a gap: 1 … 4 5 6 … 12 */
function pageNumbers(current: number, pages: number): (number | null)[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const c = current + 1;
  const around = [c - 1, c, c + 1].filter((n) => n > 1 && n < pages);
  const out: (number | null)[] = [1];
  if (around[0] > 2) out.push(null);
  out.push(...around);
  if (around[around.length - 1] < pages - 1) out.push(null);
  out.push(pages);
  return out;
}

/**
 * Rows per page · Showing 26 to 50 of 120 · Previous 1 … 4 5 6 … 12 Next.
 * `page` is 0-based. Without `onPageSize` there is no rows-per-page choice and nothing renders when
 * everything fits on one page. When the list shrinks (an item was approved or removed) and `page` is
 * past the end, it moves back to the last page that still has items. Keep it mounted when the page is
 * empty so that can happen.
 */
export function Pager({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
  className,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  onPageSize?: (size: number) => void;
  pageSizeOptions?: number[];
  className?: string;
}) {
  const sizeId = useId();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  useEffect(() => {
    if (total > 0 && page > pages - 1) onPage(pages - 1);
  }, [total, page, pages, onPage]);
  const options = pageSizeOptions.includes(pageSize)
    ? pageSizeOptions
    : [...pageSizeOptions, pageSize].sort((a, b) => a - b);
  // The size choice stays visible while a smaller size would still split the list into pages
  const showSize = !!onPageSize && total > Math.min(...options);
  if (total <= pageSize && !showSize) return null;
  const current = Math.min(page, pages - 1);
  const from = total ? current * pageSize + 1 : 0;
  const to = Math.min(total, (current + 1) * pageSize);
  return (
    <nav
      aria-label="Pagination"
      className={cn(
        "mt-4 flex flex-col gap-2 text-xs sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <div className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1">
        {showSize && (
          <span className="flex items-center gap-1.5">
            <label htmlFor={sizeId}>Rows per page</label>
            <select
              id={sizeId}
              value={pageSize}
              onChange={(e) => onPageSize(Number(e.target.value))}
              className="border-border bg-background text-foreground h-7 border px-1.5 text-xs"
            >
              {options.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </span>
        )}
        <span aria-live="polite">
          Showing {from.toLocaleString("en")} to {to.toLocaleString("en")} of {total.toLocaleString("en")}
        </span>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between gap-1 sm:justify-end">
          <Button
            variant="outline"
            size="sm"
            disabled={current <= 0}
            onClick={() => onPage(current - 1)}
            aria-label="Previous page"
          >
            Previous
          </Button>
          <span className="text-muted-foreground px-2 sm:hidden">
            Page {current + 1} of {pages}
          </span>
          <span className="hidden items-center gap-1 sm:flex">
            {pageNumbers(current, pages).map((n, i) =>
              n === null ? (
                <span key={`gap-${i}`} className="text-muted-foreground px-1" aria-hidden>
                  …
                </span>
              ) : (
                <Button
                  key={n}
                  variant={n === current + 1 ? "default" : "outline"}
                  size="sm"
                  className="min-w-7 px-1.5 tabular-nums"
                  onClick={() => onPage(n - 1)}
                  aria-label={`Page ${n}`}
                  aria-current={n === current + 1 ? "page" : undefined}
                >
                  {n}
                </Button>
              ),
            )}
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
        </div>
      )}
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

/**
 * Rows per page kept in a URL search param next to `useUrlPage(pageParam)`; the default removes the
 * param. Changing it goes back to the first page. Only sizes in PAGE_SIZE_OPTIONS (or the default)
 * are accepted from the URL.
 */
export function useUrlPageSize(
  defaultSize: number,
  pageParam = "page",
): [number, (size: number) => void] {
  const param = pageParam.endsWith("page") ? pageParam.replace(/page$/, "size") : `${pageParam}_size`;
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const raw = Number(params.get(param));
  const size = raw === defaultSize || PAGE_SIZE_OPTIONS.includes(raw) ? raw : defaultSize;
  const setSize = useCallback(
    (next: number) => {
      const sp = new URLSearchParams(window.location.search);
      if (next !== defaultSize) sp.set(param, String(next));
      else sp.delete(param);
      sp.delete(pageParam);
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, param, pageParam, defaultSize],
  );
  return [size, setSize];
}
