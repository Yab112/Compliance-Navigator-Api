import { cn } from "@cn/core/lib/utils";
import { TIMELINE, timelineIndex, type HireStage } from "@/lib/hire-stage";

/** Requested · Accepted · Paid · In progress · Delivered · Closed, with the current step marked. */
export function HireTimeline({ stage, next }: { stage: HireStage; next: string }) {
  if (stage === "declined" || stage === "cancelled") {
    return <p className="text-muted-foreground mt-2 text-xs">{next}</p>;
  }
  // Closed jobs are history: the badge and price line say it all, and older jobs may not have gone
  // through every step (e.g. paid outside the platform), so don't draw steps they never took
  if (stage === "closed" || stage === "reviewed") {
    return next ? <p className="text-muted-foreground mt-2 text-xs">{next}</p> : null;
  }
  const at = timelineIndex(stage);
  const done = false;
  return (
    <div className="mt-3">
      <ol className="flex items-center gap-1 overflow-x-auto pb-1 text-[11px] [scrollbar-width:none]" aria-label="Progress">
        {TIMELINE.map((step, i) => {
          const passed = i < at || (done && i === at);
          const current = i === at && !done;
          return (
            <li key={step.key} className="flex shrink-0 items-center gap-1">
              <span
                aria-current={current ? "step" : undefined}
                className={cn(
                  "flex items-center gap-1 rounded-full px-2 py-0.5",
                  passed && "bg-primary/10 text-primary",
                  current && "bg-primary font-semibold text-white",
                  !passed && !current && "text-muted-foreground",
                )}
              >
                {passed ? "✓" : `${i + 1}`} {step.label}
              </span>
              {i < TIMELINE.length - 1 && <span className="bg-border h-px w-3" aria-hidden />}
            </li>
          );
        })}
      </ol>
      {next && (
        <p className="border-primary bg-secondary/40 mt-2 border-l-2 px-3 py-1.5 text-xs">
          <span className="font-semibold">Next: </span>
          {next}
        </p>
      )}
    </div>
  );
}
