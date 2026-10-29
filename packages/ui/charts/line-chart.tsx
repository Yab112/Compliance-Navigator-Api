"use client";

import { useId, useMemo, useState } from "react";
import { cn } from "@cn/core/lib/utils";
import { ChartTheme, SERIES_COLORS, compactNumber } from "./chart-theme";

export type LineSeries = { name: string; values: number[] };

type LineChartProps = {
  /** X labels (one per point), e.g. ISO days */
  labels: string[];
  series: LineSeries[];
  formatLabel?: (label: string) => string;
  height?: number;
  className?: string;
  ariaLabel: string;
};

const PAD = { top: 12, right: 12, bottom: 22, left: 32 };
const WIDTH = 640;

function niceMax(max: number) {
  if (max <= 4) return 4;
  const pow = 10 ** Math.floor(Math.log10(max));
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => max / s <= 4) ?? pow * 10;
  return Math.ceil(max / step) * step;
}

/** Multi-series line chart: 2px lines, ~10% area wash, crosshair + tooltip, legend for ≥2 series. */
export function LineChart({
  labels,
  series,
  formatLabel = (l) => l,
  height = 200,
  className,
  ariaLabel,
}: LineChartProps) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);
  const n = labels.length;
  const max = useMemo(() => niceMax(Math.max(0, ...series.flatMap((s) => s.values))), [series]);
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max];

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = ((e.clientX - rect.left) / rect.width) * WIDTH - PAD.left;
    const i = Math.round((rel / innerW) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  };

  if (n === 0) return null;

  return (
    <div className={cn("viz-root relative", className)}>
      <ChartTheme />
      {series.length > 1 && (
        <ul className="text-muted-foreground mb-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
          {series.map((s, si) => (
            <li key={s.name} className="flex items-center gap-1.5">
              <span className="h-0.5 w-3 rounded" style={{ background: SERIES_COLORS[si] }} />
              {s.name}
            </li>
          ))}
        </ul>
      )}
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="h-auto w-full overflow-visible"
        role="img"
        aria-label={ariaLabel}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--viz-grid)" strokeWidth={1} />
            <text x={PAD.left - 6} y={y(t)} dy="0.32em" textAnchor="end" className="fill-muted-foreground text-[10px]">
              {compactNumber(t)}
            </text>
          </g>
        ))}
        {[0, Math.floor((n - 1) / 2), n - 1].map((i) => (
          <text key={i} x={x(i)} y={height - 6} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"} className="fill-muted-foreground text-[10px]">
            {formatLabel(labels[i])}
          </text>
        ))}
        {series.map((s, si) => {
          const pts = s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
          const area = `${x(0)},${y(0)} ${pts} ${x(n - 1)},${y(0)}`;
          return (
            <g key={s.name}>
              <polygon points={area} fill={SERIES_COLORS[si]} opacity={0.1} />
              <polyline points={pts} fill="none" stroke={SERIES_COLORS[si]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            </g>
          );
        })}
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} stroke="var(--muted-foreground)" strokeWidth={1} opacity={0.5} />
            {series.map((s, si) => (
              <circle key={s.name} cx={x(hover)} cy={y(s.values[hover] ?? 0)} r={4} fill={SERIES_COLORS[si]} stroke="var(--viz-surface)" strokeWidth={2} />
            ))}
          </g>
        )}
        <rect
          x={PAD.left}
          y={PAD.top}
          width={innerW}
          height={innerH}
          fill="transparent"
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
          aria-describedby={`${id}-tip`}
        />
      </svg>
      {hover !== null && (
        <div
          id={`${id}-tip`}
          role="tooltip"
          className="bg-popover text-popover-foreground ring-foreground/10 pointer-events-none absolute top-6 z-10 min-w-32 px-2.5 py-2 text-[11px] ring-1"
          style={{
            left: `${(x(hover) / WIDTH) * 100}%`,
            transform: x(hover) > WIDTH / 2 ? "translateX(calc(-100% - 8px))" : "translateX(8px)",
          }}
        >
          <p className="mb-1 font-medium">{formatLabel(labels[hover])}</p>
          {series.map((s, si) => (
            <p key={s.name} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-full" style={{ background: SERIES_COLORS[si] }} />
                {s.name}
              </span>
              <span className="font-medium tabular-nums">{s.values[hover] ?? 0}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
