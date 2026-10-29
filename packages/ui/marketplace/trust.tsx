"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge } from "../badge";
import { cn } from "@cn/core/lib/utils";
import type { HireStatus, PublicProvider, ScorePart } from "@cn/core/types/provider";
import { HIRE_STATUS, TYPE_META, specialtyLabel } from "./constants";

function scoreTone(score: number) {
  if (score >= 75) return "bg-emerald-600 text-white";
  if (score >= 55) return "bg-primary text-primary-foreground";
  if (score >= 40) return "bg-amber-500 text-white";
  return "bg-zinc-500 text-white";
}

/** Points per factor; used in the score popover and on profile pages. */
export function ScoreBreakdown({ parts, compact }: { parts: ScorePart[]; compact?: boolean }) {
  return (
    <ul className={cn("space-y-2", compact ? "text-[11px]" : "text-xs")}>
      {parts.map((p) => {
        const pct = p.max > 0 ? Math.max(0, Math.min(100, (p.points / p.max) * 100)) : 100;
        return (
          <li key={p.key}>
            <div className="flex justify-between gap-3 font-medium">
              <span>{p.label}</span>
              <span className={cn("tabular-nums", p.points < 0 && "text-destructive")}>
                {p.points > 0 && p.key === "penalties" ? "+" : ""}
                {p.points}
                {p.max > 0 && <span className="text-muted-foreground font-normal"> / {p.max}</span>}
              </span>
            </div>
            {p.max > 0 && (
              <div className="bg-muted mt-1 h-1.5 overflow-hidden rounded-full" aria-hidden>
                <div className="bg-primary h-full rounded-full" style={{ width: `${pct}%` }} />
              </div>
            )}
            <p className="text-muted-foreground mt-0.5">{p.detail}</p>
          </li>
        );
      })}
    </ul>
  );
}

/** Trust score chip; click to see how it was calculated. */
export function ScoreBadge({
  score,
  parts,
  isNew,
  size = "md",
}: {
  score: number;
  parts?: ScorePart[];
  isNew?: boolean;
  size?: "md" | "lg";
}) {
  const [open, setOpen] = useState(false);
  const chip = (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md font-bold tabular-nums",
        scoreTone(score),
        size === "lg" ? "px-3 py-1.5 text-lg" : "px-2 py-0.5 text-xs",
      )}
    >
      {score}
      <span className={cn("font-medium opacity-80", size === "lg" ? "text-xs" : "text-[10px]")}>/100</span>
    </span>
  );
  return (
    <span className="relative inline-flex items-center gap-1.5">
      {parts?.length ? (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          title="Trust score: click for the breakdown"
          className="focus-visible:ring-ring rounded-md focus-visible:ring-2"
        >
          {chip}
        </button>
      ) : (
        chip
      )}
      {isNew && <Badge variant="outline" className="text-[10px]">New</Badge>}
      {open && parts && (
        <span className="border-border bg-popover absolute top-full left-0 z-30 mt-2 block w-72 rounded-md border p-4 text-left shadow-lg">
          <span className="mb-3 flex items-center justify-between">
            <span className="text-sm font-semibold">Trust score {score}/100</span>
            <button type="button" className="text-muted-foreground text-xs hover:underline" onClick={() => setOpen(false)}>
              Close
            </button>
          </span>
          <ScoreBreakdown parts={parts} compact />
          <Link href="/hire/how-scores-work" className="text-primary mt-3 block text-xs font-medium hover:underline">
            How scores work
          </Link>
        </span>
      )}
    </span>
  );
}

export function TypeBadge({ type, entity }: { type: PublicProvider["provider_type"]; entity: PublicProvider["entity_type"] }) {
  return (
    <Badge variant="outline" className="text-[10px]">
      {TYPE_META[type].label} · {entity === "company" ? "Company" : "Individual"}
    </Badge>
  );
}

/** What has been checked: Fayda ID, business registration, sector licence. */
export function VerificationBadges({ provider }: { provider: Pick<PublicProvider, "id_verified" | "registered_business" | "external_license_status" | "external_license_type" | "entity_type"> }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {provider.id_verified && (
        <Badge className="bg-emerald-100 text-[10px] text-emerald-900" title="National ID verified with Fayda">
          ✓ ID verified
        </Badge>
      )}
      {provider.registered_business && (
        <Badge className="bg-emerald-100 text-[10px] text-emerald-900" title="TIN and trade licence on file">
          ✓ {provider.entity_type === "company" ? "Registered company" : "TIN on file"}
        </Badge>
      )}
      {provider.external_license_status === "verified" && (
        <Badge className="bg-emerald-100 text-[10px] text-emerald-900" title={provider.external_license_type ?? "Sector licence"}>
          ✓ Licence checked
        </Badge>
      )}
    </span>
  );
}

export function Stars({ value, className }: { value: number; className?: string }) {
  const rounded = Math.round(value);
  return (
    <span className={cn("tracking-tight text-amber-500", className)} aria-label={`${value.toFixed(1)} out of 5`}>
      {"★".repeat(rounded)}
      <span className="text-muted-foreground/40">{"★".repeat(5 - rounded)}</span>
    </span>
  );
}

export function RatingSummary({ value, count }: { value: number; count: number }) {
  if (!count) return <span className="text-muted-foreground text-xs">No reviews yet</span>;
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <Stars value={value} />
      <span className="font-semibold">{value.toFixed(1)}</span>
      <span className="text-muted-foreground">({count} review{count === 1 ? "" : "s"})</span>
    </span>
  );
}

export function StarInput({ value, onChange, label, size = "md" }: { value: number; onChange: (v: number) => void; label: string; size?: "sm" | "md" }) {
  return (
    <span role="radiogroup" aria-label={label} className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          onClick={() => onChange(n)}
          className={cn(size === "md" ? "text-2xl" : "text-lg", n <= value ? "text-amber-500" : "text-muted-foreground/30", "leading-none")}
        >
          ★
        </button>
      ))}
    </span>
  );
}

export function HireStatusBadge({ status }: { status: HireStatus }) {
  const s = HIRE_STATUS[status];
  return <Badge className={s.className}>{s.label}</Badge>;
}

export function SpecialtyChips({ keys }: { keys: string[] }) {
  if (!keys.length) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {keys.map((k) => (
        <span key={k} className="bg-secondary text-secondary-foreground rounded px-1.5 py-0.5 text-[11px]">
          {specialtyLabel(k, true)}
        </span>
      ))}
    </span>
  );
}
