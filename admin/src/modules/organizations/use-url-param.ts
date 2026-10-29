"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/**
 * Filters kept in the URL, so Back, refresh and shared links keep the tab and search.
 * Setting a filter also goes back to the first page. A value equal to the fallback is left out.
 * Components using this need a <Suspense> boundary because of useSearchParams.
 */
export function useUrlParams<K extends string>(fallbacks: Record<K, string>) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const values = Object.fromEntries(
    (Object.keys(fallbacks) as K[]).map((k) => [k, params.get(k) ?? fallbacks[k]]),
  ) as Record<K, string>;
  const set = useCallback(
    (changes: Partial<Record<K, string>>) => {
      const sp = new URLSearchParams(window.location.search);
      for (const [k, v] of Object.entries(changes) as [K, string | undefined][]) {
        if (v === undefined || v === fallbacks[k]) sp.delete(k);
        else sp.set(k, v);
      }
      sp.delete("page");
      const qs = sp.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    // fallbacks is a literal at the call site; its contents never change
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [router, pathname],
  );
  return [values, set] as const;
}
