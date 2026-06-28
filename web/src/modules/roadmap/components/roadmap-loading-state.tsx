import { Spinner } from "@/components/ui/spinner";

export function RoadmapLoadingState() {
  return (
    <div
      className="border-border flex flex-col items-center justify-center gap-3 border px-6 py-16"
      role="status"
      aria-live="polite"
    >
      <Spinner className="size-6" />
      <p className="text-muted-foreground text-sm">Loading your path…</p>
    </div>
  );
}
