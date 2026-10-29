import Link from "next/link";
import { cn } from "@/lib/utils";
import type { ServicePath } from "@/types/organizations";
import { formatFee, formatMinutes } from "./shared";

/**
 * The cross-organization chain for one service: every service to finish first,
 * in order, each card naming the organization that gives it.
 */
export function PathFlow({ path }: { path: ServicePath }) {
  const fee = path.steps.reduce((sum, s) => sum + (s.fee_amount_min ?? 0), 0);
  return (
    <div>
      <p className="text-muted-foreground mb-4 text-sm">
        {path.steps.length} step{path.steps.length === 1 ? "" : "s"} across{" "}
        <strong className="text-foreground">
          {path.organizations} organization{path.organizations === 1 ? "" : "s"}
        </strong>
        {path.total_minutes > 0 && <> · about {formatMinutes(path.total_minutes)} at the windows</>}
        {fee > 0 && <> · from {fee.toLocaleString("en")} ETB in fees</>}
      </p>
      <ol className="flex flex-col gap-0 lg:flex-row lg:flex-wrap lg:items-stretch">
        {path.steps.map((step, i) => (
          <li key={step.service_id} className="flex flex-col lg:flex-row lg:items-center">
            <div
              className={cn(
                "w-full rounded-md border p-4 lg:w-60",
                step.is_target ? "border-primary bg-secondary/60" : "border-border bg-card",
              )}
            >
              <p className="text-muted-foreground text-[11px] font-semibold tracking-wide uppercase">
                Step {i + 1}
                {step.is_target && " · your goal"}
              </p>
              <Link
                href={`/organizations/${step.org.slug}/services/${step.slug}`}
                className="text-gov-ink mt-1 block font-semibold hover:underline"
              >
                {step.name}
              </Link>
              <Link href={`/organizations/${step.org.slug}`} className="text-primary text-xs hover:underline">
                {step.org.name}
              </Link>
              <p className="text-muted-foreground mt-2 text-xs">
                {formatFee(step.fee_amount_min, step.fee_amount_max, step.fee_currency)} ·{" "}
                {step.processing_time_text || formatMinutes(step.processing_minutes)}
              </p>
              {step.provides.length > 0 && (
                <p className="mt-2 text-xs">
                  Gives you: <span className="font-medium">{Array.from(new Set(step.provides)).join(", ")}</span>
                </p>
              )}
            </div>
            {i < path.steps.length - 1 && (
              <span className="text-primary flex h-8 items-center justify-center text-lg lg:h-auto lg:w-8" aria-hidden>
                <span className="lg:hidden">↓</span>
                <span className="hidden lg:inline">→</span>
              </span>
            )}
          </li>
        ))}
      </ol>
      {path.cycles.length > 0 && (
        <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Some requirements depend on each other in a loop ({path.cycles.map((c) => c.join(" → ")).join("; ")}). Ask
          the office which one to start with.
        </p>
      )}
    </div>
  );
}
