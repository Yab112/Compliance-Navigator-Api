import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Tone = "good" | "warning" | "critical" | "neutral" | "info";

const TONE_CLASS: Record<Tone, string> = {
  good: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  warning: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  critical: "bg-destructive/10 text-destructive",
  neutral: "bg-muted text-muted-foreground",
  info: "bg-sky-500/10 text-sky-700 dark:text-sky-400",
};

const ICON: Record<Tone, string> = { good: "●", warning: "▲", critical: "■", neutral: "○", info: "◆" };

const STATUS_TONE: Record<string, Tone> = {
  success: "good",
  resolved: "good",
  approved: "good",
  running: "info",
  open: "warning",
  pending: "warning",
  failed: "critical",
  dismissed: "neutral",
};

/** Status always carries an icon + label, never color alone. */
export function StatusBadge({ status, tone, className }: { status: string; tone?: Tone; className?: string }) {
  const t = tone ?? STATUS_TONE[status] ?? "neutral";
  return (
    <Badge variant="secondary" className={cn("gap-1 capitalize", TONE_CLASS[t], className)}>
      <span aria-hidden className="text-[8px]">
        {ICON[t]}
      </span>
      {status.replace(/_/g, " ")}
    </Badge>
  );
}
