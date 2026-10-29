import { cn } from "@cn/core/lib/utils";
import { PRIORITY_LABELS, STATUS_LABELS, type TicketPriority, type TicketStatus } from "@cn/core/types/support";

const STATUS_CLASS: Record<TicketStatus, string> = {
  new: "bg-gov-yellow text-gov-ink",
  open: "bg-amber-100 text-amber-900",
  waiting_customer: "bg-sky-100 text-sky-900",
  resolved: "bg-primary/15 text-primary",
  closed: "bg-muted text-muted-foreground",
};

const STATUS_ICON: Record<TicketStatus, string> = { new: "●", open: "▲", waiting_customer: "◆", resolved: "✓", closed: "○" };

/** Status always carries an icon and a label, never colour alone. */
export function TicketStatusBadge({ status, label, className }: { status: TicketStatus; label?: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap", STATUS_CLASS[status], className)}>
      <span aria-hidden className="text-[8px]">
        {STATUS_ICON[status]}
      </span>
      {label ?? STATUS_LABELS[status]}
    </span>
  );
}

const PRIORITY_CLASS: Record<TicketPriority, string> = {
  low: "border-border text-muted-foreground",
  normal: "border-border",
  high: "border-amber-400 text-amber-800",
  urgent: "border-destructive bg-destructive/10 text-destructive font-semibold",
};

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  return (
    <span className={cn("inline-flex rounded border px-1.5 py-0.5 text-[11px] whitespace-nowrap", PRIORITY_CLASS[priority])}>
      {PRIORITY_LABELS[priority]}
    </span>
  );
}

function minutesUntil(iso: string): number {
  return Math.round((new Date(iso).getTime() - Date.now()) / 60000);
}

/** Time left before the first-response target, or how late it is. */
export function SlaBadge({ due, overdue, done }: { due: string; overdue: boolean; done?: boolean }) {
  if (done) return null;
  const minutes = minutesUntil(due);
  const span = Math.abs(minutes);
  const text = span >= 1440 ? `${Math.round(span / 1440)} d` : span >= 60 ? `${Math.round(span / 60)} h` : `${span} min`;
  return overdue || minutes < 0 ? (
    <span className="bg-destructive/10 text-destructive inline-flex rounded px-1.5 py-0.5 text-[11px] font-semibold whitespace-nowrap">
      ■ Overdue {text}
    </span>
  ) : (
    <span
      className={cn(
        "inline-flex rounded px-1.5 py-0.5 text-[11px] whitespace-nowrap",
        minutes < 120 ? "bg-amber-100 text-amber-900" : "text-muted-foreground",
      )}
    >
      Due in {text}
    </span>
  );
}
