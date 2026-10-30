import { Button } from "@cn/ui/button";
import { Spinner } from "@cn/ui/spinner";
import { cn } from "@cn/core/lib/utils";

export function LoadingState({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div className={cn("text-muted-foreground flex items-center justify-center gap-2 py-12 text-xs", className)}>
      <Spinner /> {label}
    </div>
  );
}

/** HTTP status of a failed request, if the error carries one. */
export function errorStatus(error: unknown): number | undefined {
  const status = (error as { response?: { status?: unknown } } | null | undefined)?.response?.status;
  return typeof status === "number" ? status : undefined;
}

/** The one "no permission" state used on every page. */
export function NoAccessState({ className }: { className?: string }) {
  return (
    <div className={cn("border-border text-muted-foreground border border-dashed px-4 py-10 text-center text-xs", className)}>
      <p className="text-foreground font-medium">You don&apos;t have access to this page</p>
      <p className="mt-1">Ask a Super admin if you need it for your work.</p>
    </div>
  );
}

/**
 * A failed load. Pass `error` so a refusal (403) shows the no-access state and "Try again" is only
 * offered when trying again can help (network trouble or a server error, not 403/404 or other 4xx).
 */
export function ErrorState({ message, onRetry, error }: { message: string; onRetry?: () => void; error?: unknown }) {
  const status = errorStatus(error);
  if (status === 403) return <NoAccessState />;
  const retryable = status === undefined ? !/not found/i.test(message) : status >= 500 || status === 408 || status === 429;
  return (
    <div className="border-destructive/30 bg-destructive/5 flex flex-col items-start gap-2 border p-4 text-xs">
      <p className="text-destructive font-medium">{status === 404 || (status === undefined && !retryable) ? "Not found" : "Couldn't load this data"}</p>
      <p className="text-muted-foreground">{message}</p>
      {onRetry && retryable && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="border-border text-muted-foreground border border-dashed px-4 py-10 text-center text-xs">
      <p className="text-foreground font-medium">{title}</p>
      {description && <p className="mt-1">{description}</p>}
    </div>
  );
}
