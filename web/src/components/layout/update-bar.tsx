"use client";

import { useEffect, useState } from "react";

const CHECK_EVERY_MS = 60_000;

/** After we release an update, pages opened earlier offer a reload instead of running old code. */
export function UpdateBar() {
  const [stale, setStale] = useState(false);

  useEffect(() => {
    const mine = process.env.NEXT_PUBLIC_BUILD_ID;
    if (!mine) return;
    let stopped = false;
    const check = async () => {
      if (stopped || document.visibilityState !== "visible") return;
      try {
        const res = await fetch("/api/version", { cache: "no-store" });
        const { buildId } = (await res.json()) as { buildId: string | null };
        if (buildId && buildId !== mine) setStale(true);
      } catch {}
    };
    const timer = setInterval(check, CHECK_EVERY_MS);
    document.addEventListener("visibilitychange", check);
    void check();
    return () => {
      stopped = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", check);
    };
  }, []);

  if (!stale) return null;
  return (
    <div role="status" className="bg-gov-ink fixed inset-x-0 bottom-0 z-[80] flex flex-wrap items-center justify-center gap-3 px-4 py-3 text-sm text-white shadow-lg">
      <span>A new version of Compliance Navigator is available · አዲስ ስሪት አለ</span>
      <button type="button" onClick={() => window.location.reload()} className="bg-gov-yellow text-gov-ink rounded-md px-4 py-1.5 font-semibold hover:brightness-95">
        Reload
      </button>
    </div>
  );
}
