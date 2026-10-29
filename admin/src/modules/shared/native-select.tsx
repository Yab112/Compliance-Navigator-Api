import { cn } from "@cn/core/lib/utils";

/** Compact native select styled like the shadcn inputs (works well inside tables). */
export function NativeSelect({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "border-input dark:bg-input/30 focus-visible:border-ring focus-visible:ring-ring/50 h-8 rounded-none border bg-transparent px-2 text-xs outline-none focus-visible:ring-1 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
