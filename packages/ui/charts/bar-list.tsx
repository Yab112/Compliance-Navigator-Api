"use client";

import { cn } from "@cn/core/lib/utils";
import { ChartTheme, SERIES_COLORS } from "./chart-theme";

export type BarDatum = { label: string; value: number; href?: string };

type BarListProps = {
  data: BarDatum[];
  /** Single-series magnitude bars all wear one hue (slot 1) */
  colorIndex?: number;
  className?: string;
  ariaLabel: string;
  formatValue?: (v: number) => string;
};

/** Horizontal bars, ≤ 12px thick with rounded data-ends; value at the tip, title on hover. */
export function BarList({ data, colorIndex = 0, className, ariaLabel, formatValue = String }: BarListProps) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className={cn("viz-root", className)} role="list" aria-label={ariaLabel}>
      <ChartTheme />
      {data.map((d) => (
        <div key={d.label} role="listitem" className="group grid grid-cols-[minmax(0,9rem)_1fr] items-center gap-3 py-1" title={`${d.label}: ${formatValue(d.value)}`}>
          <span className="text-muted-foreground truncate text-[11px]">{d.label}</span>
          <div className="flex items-center gap-2">
            <div
              className="h-3 min-w-0.5 rounded-r-[4px] transition-opacity group-hover:opacity-80"
              style={{ width: `${(d.value / max) * 85}%`, background: SERIES_COLORS[colorIndex] }}
            />
            <span className="text-[11px] font-medium tabular-nums">{formatValue(d.value)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
