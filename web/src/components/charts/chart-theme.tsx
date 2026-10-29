/**
 * Chart tokens from the validated dataviz reference palette (categorical slots in
 * fixed order). Light and dark are separately selected steps, not a flip.
 */
const CHART_CSS = `
.viz-root {
  --viz-series-1: #2a78d6;
  --viz-series-2: #eb6834;
  --viz-series-3: #1baf7a;
  --viz-series-4: #eda100;
  --viz-grid: oklch(0.922 0 0);
  --viz-surface: var(--background);
}
.dark .viz-root {
  --viz-series-1: #3987e5;
  --viz-series-2: #d95926;
  --viz-series-3: #199e70;
  --viz-series-4: #c98500;
  --viz-grid: oklch(1 0 0 / 12%);
}
`;

export const SERIES_COLORS = [
  "var(--viz-series-1)",
  "var(--viz-series-2)",
  "var(--viz-series-3)",
  "var(--viz-series-4)",
] as const;

export function ChartTheme() {
  return <style>{CHART_CSS}</style>;
}

export function compactNumber(n: number): string {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}
