"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { PROCESS_GOALS } from "@/data/process-graph";
import { cn } from "@/lib/utils";
import { SearchDropdown } from "./search-dropdown";

export const QUICK_GOALS = [
  { id: "passport", label: "Passport" },
  { id: "kebele_id", label: "Kebele ID" },
  { id: "trade_license", label: "Trade license" },
] as const;

type GoalPickerProps = {
  value: string;
  onChange: (goalId: string) => void;
};

export function GoalPicker({ value, onChange }: GoalPickerProps) {
  const [search, setSearch] = useState("");
  const [focused, setFocused] = useState(false);

  const selected = PROCESS_GOALS.find((g) => g.id === value);
  const q = search.trim().toLowerCase();
  const showList = focused && q.length > 0;

  const filtered = useMemo(() => {
    if (!q) return [];
    return PROCESS_GOALS.filter(
      (g) =>
        g.label.toLowerCase().includes(q) ||
        g.id.replace(/_/g, " ").includes(q),
    );
  }, [q]);

  function pick(id: string) {
    onChange(id);
    setSearch("");
    setFocused(false);
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {QUICK_GOALS.map((item) => {
          const active = value === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => pick(item.id)}
              onMouseDown={(e) => e.preventDefault()}
              className={cn(
                "rounded-lg border px-4 py-4 text-sm font-medium",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
                active
                  ? "border-primary bg-primary/5 ring-1 ring-primary"
                  : "border-border bg-background",
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      <div className="min-h-5">
        {selected && (
          <p className="text-sm">
            <span className="text-muted-foreground">Selected: </span>
            <span className="font-medium">{selected.label}</span>
          </p>
        )}
      </div>

      <div className="relative z-50 isolate">
        <Input
          id="goal-search"
          placeholder="TIN, registration, birth certificate…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 200)}
          autoComplete="off"
          className="h-11"
        />

        <SearchDropdown open={showList}>
          {filtered.length === 0 ? (
            <li className="text-muted-foreground px-3 py-3 text-sm">
              Nothing found. Try another word.
            </li>
          ) : (
            filtered.map((g) => (
              <li key={g.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={value === g.id}
                  className={cn(
                    "w-full px-3 py-2.5 text-left text-sm",
                    value === g.id && "bg-primary/10 font-medium",
                  )}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(g.id)}
                >
                  {g.label}
                </button>
              </li>
            ))
          )}
        </SearchDropdown>
      </div>
    </div>
  );
}
