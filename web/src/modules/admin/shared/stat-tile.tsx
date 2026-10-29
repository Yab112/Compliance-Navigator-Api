import Link from "next/link";
import { cn } from "@/lib/utils";

type StatTileProps = {
  label: string;
  value: string | number;
  hint?: React.ReactNode;
  href?: string;
  tone?: "default" | "attention";
  className?: string;
};

/** KPI tile: label · value · optional context line. */
export function StatTile({ label, value, hint, href, tone = "default", className }: StatTileProps) {
  const body = (
    <div
      className={cn(
        "ring-foreground/10 bg-card flex h-full flex-col gap-1 p-3 ring-1",
        href && "hover:bg-muted/50 transition-colors",
        tone === "attention" && "ring-amber-500/50",
        className,
      )}
    >
      <p className="text-muted-foreground text-[11px]">{label}</p>
      <p className="text-xl font-semibold tabular-nums">
        {typeof value === "number" ? value.toLocaleString("en") : value}
      </p>
      {hint && <p className="text-muted-foreground text-[11px] leading-snug">{hint}</p>}
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}
