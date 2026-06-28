"use client";

import { cn } from "@/lib/utils";

type SearchDropdownProps = {
  open: boolean;
  children: React.ReactNode;
  className?: string;
};

/** Absolutely positioned list — does not shift layout below */
export function SearchDropdown({
  open,
  children,
  className,
}: SearchDropdownProps) {
  if (!open) return null;

  return (
    <ul
      role="listbox"
      className={cn(
        "border-border absolute top-full right-0 left-0 z-50 mt-1 max-h-44 overflow-y-auto rounded-lg border bg-background",
        className,
      )}
    >
      {children}
    </ul>
  );
}
