"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import {
  ADDIS_SUB_CITIES,
  POPULAR_SUB_CITIES,
  filterLocations,
  getLocationLabel,
} from "@/constants/addis-locations";
import { cn } from "@/lib/utils";
import { SearchDropdown } from "./search-dropdown";

type SubCityPickerProps = {
  value: string;
  onChange: (subCity: string) => void;
};

export function SubCityPicker({ value, onChange }: SubCityPickerProps) {
  const [search, setSearch] = useState("");
  const [focused, setFocused] = useState(false);

  const selectedLabel = getLocationLabel(value);
  const filtered = useMemo(() => filterLocations(search), [search]);
  const showList = focused;

  function pick(subCity: string) {
    onChange(subCity);
    setSearch("");
    setFocused(false);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {POPULAR_SUB_CITIES.map((id) => {
          const loc = ADDIS_SUB_CITIES.find((l) => l.value === id);
          if (!loc) return null;
          const active = value === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => pick(id)}
              onMouseDown={(e) => e.preventDefault()}
              className={cn(
                "rounded-lg border px-3 py-2 text-sm font-medium",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
                active
                  ? "border-primary bg-primary/5 ring-1 ring-primary"
                  : "border-border bg-background",
              )}
            >
              {loc.label}
            </button>
          );
        })}
      </div>

      <div className="min-h-5">
        <p className="text-sm">
          <span className="text-muted-foreground">Selected: </span>
          <span className="font-medium">{selectedLabel}</span>
        </p>
      </div>

      <div className="relative z-50 isolate">
        <Input
          id="sub-city-search"
          placeholder="Bole, Merkato, Piassa, Yeka…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 200)}
          autoComplete="off"
          className="h-11"
        />

        <SearchDropdown open={showList} className="max-h-52">
          {filtered.length === 0 ? (
            <li className="text-muted-foreground px-3 py-3 text-sm">
              Nothing found. Try another name.
            </li>
          ) : (
            filtered.map((loc) => (
              <li key={loc.value}>
                <button
                  type="button"
                  role="option"
                  aria-selected={value === loc.value}
                  className={cn(
                    "w-full px-3 py-2.5 text-left text-sm",
                    value === loc.value && "bg-primary/10 font-medium",
                  )}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(loc.value)}
                >
                  {loc.label}
                </button>
              </li>
            ))
          )}
        </SearchDropdown>
      </div>
    </div>
  );
}
