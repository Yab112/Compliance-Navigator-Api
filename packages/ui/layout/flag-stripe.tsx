import { cn } from "@cn/core/lib/utils";

/** Green–yellow–red band used across Ethiopian public-service sites. */
export function FlagStripe({ className }: { className?: string }) {
  return (
    <div className={cn("flex h-1", className)} aria-hidden>
      <span className="bg-gov-green flex-1" />
      <span className="bg-gov-yellow flex-1" />
      <span className="bg-gov-red flex-1" />
    </div>
  );
}
