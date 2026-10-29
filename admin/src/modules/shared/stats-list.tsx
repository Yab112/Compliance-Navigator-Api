import { humanize } from "@cn/core/lib/format";

function render(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return value.toLocaleString("en");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${humanize(k)} ${render(v)}`)
      .join(" · ");
  }
  return String(value);
}

/** Compact "key: value" rendering of a run's stats JSON. */
export function StatsList({ stats }: { stats: Record<string, unknown> | null | undefined }) {
  const entries = Object.entries(stats ?? {});
  if (!entries.length) return <span className="text-muted-foreground">-</span>;
  return (
    <dl className="flex flex-wrap gap-x-3 gap-y-0.5">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-1">
          <dt className="text-muted-foreground">{humanize(k)}:</dt>
          <dd className="font-medium tabular-nums">{render(v)}</dd>
        </div>
      ))}
    </dl>
  );
}
