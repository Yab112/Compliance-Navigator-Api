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

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="border-destructive/30 bg-destructive/5 flex flex-col items-start gap-2 border p-4 text-xs">
      <p className="text-destructive font-medium">Couldn&apos;t load this data</p>
      <p className="text-muted-foreground">{message}</p>
      {onRetry && (
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
