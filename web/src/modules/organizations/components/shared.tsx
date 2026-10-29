import { apiAssetUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ORG_TYPE_LABEL,
  SERVICE_STATUS_LABEL,
  type OrgStatus,
  type OrgType,
  type ServiceStatus,
} from "@/types/organizations";

export function formatFee(min?: number | null, max?: number | null, currency = "ETB"): string {
  if (min == null && max == null) return "Not stated";
  if (!min && !max) return "Free";
  const fmt = (n: number) => n.toLocaleString("en", { maximumFractionDigits: 2 });
  if (min != null && max != null && max !== min) return `${fmt(min)} to ${fmt(max)} ${currency}`;
  return `${fmt((min ?? max) as number)} ${currency}`;
}

export function formatMinutes(minutes?: number | null): string {
  if (minutes == null) return "Not stated";
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 60 * 24) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m ? `${h} h ${m} min` : `${h} h`;
  }
  const days = Math.round(minutes / (60 * 24));
  return `${days} day${days === 1 ? "" : "s"}`;
}

export function OrgTypeLabel({ type, className }: { type: OrgType; className?: string }) {
  return <span className={cn("text-muted-foreground text-xs", className)}>{ORG_TYPE_LABEL[type] ?? type}</span>;
}

export function VerifiedBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "bg-secondary text-primary inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold",
        className,
      )}
    >
      ✓ Verified organization
    </span>
  );
}

const ORG_STATUS: Record<OrgStatus, { label: string; className: string }> = {
  draft: { label: "Registration not finished", className: "bg-muted text-muted-foreground" },
  pending: { label: "Pending verification", className: "bg-amber-100 text-amber-900" },
  verified: { label: "Verified", className: "bg-emerald-100 text-emerald-900" },
  rejected: { label: "Rejected", className: "bg-destructive/10 text-destructive" },
  suspended: { label: "Suspended", className: "bg-zinc-200 text-zinc-800" },
};

export function OrgStatusChip({ status }: { status: OrgStatus }) {
  const s = ORG_STATUS[status];
  return <span className={cn("rounded px-2 py-0.5 text-xs font-medium", s.className)}>{s.label}</span>;
}

const SERVICE_CHIP: Record<ServiceStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  submitted: "bg-sky-100 text-sky-900",
  published: "bg-emerald-100 text-emerald-900",
  scheduled: "bg-sky-100 text-sky-900",
  changes_requested: "bg-amber-100 text-amber-900",
  archived: "bg-zinc-200 text-zinc-700",
};

export function ServiceStatusChip({ status, isLive }: { status: ServiceStatus; isLive?: boolean }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <span className={cn("rounded px-2 py-0.5 text-xs font-medium", SERVICE_CHIP[status])}>
        {SERVICE_STATUS_LABEL[status]}
      </span>
      {isLive && status !== "published" && status !== "scheduled" && status !== "archived" && (
        <span className="rounded bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">Live version still public</span>
      )}
    </span>
  );
}

export function OrgLogo({ name, url, className }: { name: string; url?: string | null; className?: string }) {
  const src = apiAssetUrl(url);
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element -- uploaded logos are served by the API
    return <img src={src} alt="" className={cn("size-12 shrink-0 rounded-md object-contain", className)} />;
  }
  const initials = name
    .split(/\s+/)
    .filter((w) => /^[A-Za-z]/.test(w))
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
  return (
    <span
      className={cn(
        "bg-secondary text-primary flex size-12 shrink-0 items-center justify-center rounded-md text-sm font-bold",
        className,
      )}
      aria-hidden
    >
      {initials || "ORG"}
    </span>
  );
}

export const ORG_TYPE_OPTIONS = Object.entries(ORG_TYPE_LABEL) as [OrgType, string][];

/** Card section with a bilingual heading, used across organization pages. */
export function Panel({
  title,
  am,
  children,
  aside,
  className,
}: {
  title: string;
  am?: string;
  children: React.ReactNode;
  aside?: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("border-border bg-card rounded-md border", className)}>
      <header className="border-border flex flex-wrap items-center justify-between gap-2 border-b px-5 py-3">
        <h2 className="text-gov-ink font-semibold">
          {title}
          {am && <span className="text-muted-foreground text-sm font-normal"> · {am}</span>}
        </h2>
        {aside}
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}

/** Bar showing how much of what a path step needs this service has filled in. */
export function CompletenessMeter({
  completeness,
  compact,
  className,
}: {
  completeness: { score: number; missing: { key: string; label: string; core: boolean }[]; core_missing: string[] };
  compact?: boolean;
  className?: string;
}) {
  const { score, missing, core_missing } = completeness;
  const tone = core_missing.length ? "bg-amber-500" : score >= 80 ? "bg-primary" : "bg-sky-600";
  return (
    <div className={className}>
      <div className="flex items-center gap-2">
        <div className="bg-muted h-2 flex-1 overflow-hidden rounded-full" aria-hidden>
          <div className={cn("h-full rounded-full", tone)} style={{ width: `${score}%` }} />
        </div>
        <span className="text-xs font-semibold tabular-nums">{score}%</span>
      </div>
      {!compact && missing.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs">
          {missing.map((m) => (
            <li key={m.key} className={m.core ? "text-amber-800" : "text-muted-foreground"}>
              {m.core ? "▲ Needed to publish: " : "○ "}
              {m.label}
            </li>
          ))}
        </ul>
      )}
      {compact && core_missing.length > 0 && (
        <p className="mt-1 text-xs text-amber-800">Needed to publish: {core_missing.join("; ")}</p>
      )}
    </div>
  );
}

/** "Confirmed by the organization 12 days ago" or the overdue warning. */
export function ConfirmedBadge({ days, due, orgName }: { days?: number | null; due?: boolean; orgName?: string }) {
  if (due) {
    return (
      <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
        Not confirmed in over 90 days · check at the window
      </span>
    );
  }
  if (days == null) return null;
  const when = days === 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`;
  return (
    <span className="bg-secondary text-primary rounded px-2 py-0.5 text-xs font-medium">
      ✓ Confirmed by {orgName ?? "the organization"} {when}
    </span>
  );
}
