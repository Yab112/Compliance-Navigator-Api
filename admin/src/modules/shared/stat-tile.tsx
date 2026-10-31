import Link from "next/link";
import { cn } from "@cn/core/lib/utils";

type StatTileProps = {
  label: string;
  value: string | number;
  hint?: React.ReactNode;
  href?: string;
  tone?: "default" | "attention";
  className?: string;
};

/** Classes for the row that holds StatTiles: one plain strip of figures between two rules, no boxes. */
export const STAT_STRIP = "border-border grid gap-x-8 gap-y-4 border-y py-4";

/** One figure in a stat strip: label · value · optional context line. */
export function StatTile({ label, value, hint, href, tone = "default", className }: StatTileProps) {
  const body = (
    <div className={cn("group flex min-w-0 flex-col gap-0.5", className)}>
      <p className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
        {tone === "attention" && <span className="size-1.5 shrink-0 rounded-full bg-amber-500" aria-label="Needs attention" />}
        {label}
      </p>
      <p className={cn("text-xl font-semibold tabular-nums", href && "group-hover:text-primary group-hover:underline")}>
        {typeof value === "number" ? value.toLocaleString("en") : value}
      </p>
      {hint && <p className="text-muted-foreground text-[11px] leading-snug">{hint}</p>}
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}
