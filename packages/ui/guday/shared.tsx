"use client";

import { useEffect, useState } from "react";
import { Badge } from "../badge";
import { Spinner } from "../spinner";
import { ADDIS_SUB_CITIES } from "@cn/core/constants/addis-locations";
import { apiAssetUrl } from "@cn/core/lib/api";
import { cn } from "@cn/core/lib/utils";
import type { ProviderStatus as AgentStatus } from "@cn/core/types/provider";

/** Ethiopian mobile numbers: 09XXXXXXXX / 07XXXXXXXX or +2519… / +2517… (mirrors the API). */
export const PHONE_RE = /^(\+251|0)[79]\d{8}$/;

export const LANGUAGE_OPTIONS = [
  { value: "am", label: "Amharic · አማርኛ" },
  { value: "en", label: "English" },
  { value: "om", label: "Afaan Oromo" },
  { value: "ti", label: "Tigrinya · ትግርኛ" },
  { value: "so", label: "Somali" },
  { value: "other", label: "Other" },
];

export function languageLabel(code: string) {
  return LANGUAGE_OPTIONS.find((l) => l.value === code)?.label.split(" · ")[0] ?? code;
}

export function subCityLabel(value?: string | null) {
  if (!value) return "-";
  return ADDIS_SUB_CITIES.find((s) => s.value === value)?.label ?? value;
}

export function formatDate(value?: string | null) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

// ---------------------------------------------------------------- form bits

type FieldProps = {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string | null;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
};

export function Field({ label, htmlFor, hint, error, required, children, className }: FieldProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-xs font-medium">
        {label}
        {required && <span className="text-destructive"> *</span>}
      </label>
      {children}
      {hint && !error && <p className="text-muted-foreground text-[11px]">{hint}</p>}
      {error && <p className="text-destructive text-[11px]">{error}</p>}
    </div>
  );
}

export function NativeSelect({
  className,
  children,
  ...props
}: React.ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "border-input focus-visible:border-ring focus-visible:ring-ring/50 dark:bg-input/30 h-8 w-full min-w-0 rounded-none border bg-transparent px-2 text-xs outline-none focus-visible:ring-1 disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function SubCityOptions({ placeholder = "Select sub-city" }: { placeholder?: string }) {
  return (
    <>
      <option value="">{placeholder}</option>
      {ADDIS_SUB_CITIES.map((s) => (
        <option key={s.value} value={s.value}>
          {s.label}
        </option>
      ))}
    </>
  );
}

// ---------------------------------------------------------------- status

const AGENT_STATUS: Record<AgentStatus, { label: string; className: string }> = {
  pending: { label: "Pending review", className: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100" },
  approved: { label: "Licensed", className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100" },
  rejected: { label: "Rejected", className: "bg-destructive/10 text-destructive" },
  suspended: { label: "Suspended", className: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200" },
};

export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const s = AGENT_STATUS[status];
  return <Badge className={s.className}>{s.label}</Badge>;
}

/** Fayda verification state: admins see the method, the public a simple tick. */
export function IdVerifiedBadge({
  method,
  verified,
  publicView,
}: {
  method?: string | null;
  verified?: boolean;
  publicView?: boolean;
}) {
  if (publicView) {
    return verified ? (
      <Badge className="bg-emerald-100 text-emerald-900" title="National ID verified with Fayda">
        ✓ ID verified
      </Badge>
    ) : null;
  }
  if (!verified) return <Badge variant="outline">Not verified</Badge>;
  if (method === "fayda_sandbox")
    return <Badge className="bg-amber-100 text-amber-900">Verified (test mode)</Badge>;
  return <Badge className="bg-emerald-100 text-emerald-900">✓ Fayda verified</Badge>;
}

// ---------------------------------------------------------------- agent visuals

export function RatingStars({
  value,
  count,
  className,
}: {
  value: number;
  count?: number;
  className?: string;
}) {
  const rounded = Math.round(value);
  return (
    <span
      className={cn("inline-flex items-center gap-1 text-xs", className)}
      aria-label={`Rated ${value.toFixed(1)} out of 5${count != null ? ` from ${count} reviews` : ""}`}
    >
      <span className="tracking-tight text-amber-500" aria-hidden>
        {"★".repeat(rounded)}
        <span className="text-muted-foreground/40">{"★".repeat(5 - rounded)}</span>
      </span>
      {count != null && (
        <span className="text-muted-foreground">
          {count > 0 ? `${value.toFixed(1)} (${count})` : "No reviews yet"}
        </span>
      )}
    </span>
  );
}

export function AgentAvatar({
  name,
  photoUrl,
  size = "md",
}: {
  name: string;
  photoUrl?: string | null;
  size?: "sm" | "md" | "lg";
}) {
  const src = apiAssetUrl(photoUrl);
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  const dims = { sm: "size-8 text-[10px]", md: "size-12 text-sm", lg: "size-20 text-xl" }[size];
  if (src) {
    // Uploaded by agents; served by the API origin, so a plain img avoids next/image domain config
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={name} className={cn(dims, "border-border shrink-0 border object-cover")} />;
  }
  return (
    <div
      className={cn(dims, "bg-primary/10 text-primary flex shrink-0 items-center justify-center font-semibold")}
      aria-hidden
    >
      {initials || "?"}
    </div>
  );
}

// ---------------------------------------------------------------- states

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="text-muted-foreground flex items-center justify-center gap-2 py-12 text-xs">
      <Spinner className="size-4" /> {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="border-destructive/30 bg-destructive/5 text-destructive border p-4 text-xs">
      {message}
      {onRetry && (
        <button type="button" onClick={onRetry} className="ml-2 underline">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="border-border border border-dashed px-4 py-12 text-center">
      <p className="text-sm font-medium">{title}</p>
      {children && <div className="text-muted-foreground mt-2 text-xs">{children}</div>}
    </div>
  );
}

export function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-[11px]">{label}</dt>
      <dd className="text-xs break-words">{children ?? "-"}</dd>
    </div>
  );
}
