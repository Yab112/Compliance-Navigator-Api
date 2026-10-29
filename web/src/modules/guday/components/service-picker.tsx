"use client";

import { useState } from "react";
import { useCatalogServices } from "@/api/catalog";
import { Input } from "@cn/ui/input";
import { Spinner } from "@cn/ui/spinner";
import type { ProviderService as AgentService } from "@cn/core/types/provider";
import { useDebounced } from "@cn/ui/guday/shared";

type ServiceSearchProps = {
  id?: string;
  placeholder?: string;
  excludeIds?: string[];
  onPick: (service: AgentService) => void;
  disabled?: boolean;
};

/** Type-ahead over the MESOB catalog. */
export function ServiceSearch({
  id,
  placeholder = "Search MESOB services (e.g. passport, TIN, lease)",
  excludeIds = [],
  onPick,
  disabled,
}: ServiceSearchProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const q = useDebounced(query.trim(), 250);
  const { data, isFetching } = useCatalogServices({ q, limit: 12 }, open && q.length >= 2);
  const items = (data?.payload.items ?? []).filter((s) => !excludeIds.includes(s.id));

  return (
    <div className="relative">
      <Input
        id={id}
        value={query}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={open && q.length >= 2}
        aria-controls={id ? `${id}-list` : undefined}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && q.length >= 2 && (
        <ul
          id={id ? `${id}-list` : undefined}
          role="listbox"
          className="border-border bg-popover absolute z-20 mt-1 max-h-64 w-full overflow-y-auto border text-xs"
        >
          {isFetching && items.length === 0 && (
            <li className="text-muted-foreground flex items-center gap-2 px-3 py-2">
              <Spinner className="size-3" /> Searching…
            </li>
          )}
          {!isFetching && items.length === 0 && (
            <li className="text-muted-foreground px-3 py-2">No matching services</li>
          )}
          {items.map((s) => (
            <li key={s.id} role="option" aria-selected={false}>
              <button
                type="button"
                className="hover:bg-muted w-full px-3 py-2 text-left"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onPick({
                    id: s.id,
                    name: s.name,
                    institution: s.institution.short_name ?? s.institution.name ?? null,
                  });
                  setQuery("");
                  setOpen(false);
                }}
              >
                <span className="font-medium">{s.name}</span>
                <span className="text-muted-foreground ml-2">
                  {s.institution.short_name ?? s.institution.name}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type ServiceMultiPickerProps = {
  id?: string;
  value: AgentService[];
  onChange: (next: AgentService[]) => void;
  max?: number;
};

export function ServiceMultiPicker({ id, value, onChange, max = 30 }: ServiceMultiPickerProps) {
  const full = value.length >= max;
  return (
    <div className="flex flex-col gap-2">
      <ServiceSearch
        id={id}
        disabled={full}
        placeholder={full ? `Maximum of ${max} services reached` : undefined}
        excludeIds={value.map((v) => v.id)}
        onPick={(s) => onChange([...value, s])}
      />
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Selected services">
          {value.map((s) => (
            <li
              key={s.id}
              className="border-border bg-muted/40 flex max-w-full items-center gap-1 border py-0.5 pr-1 pl-2 text-xs"
            >
              <span className="truncate">
                {s.name}
                {s.institution && <span className="text-muted-foreground"> · {s.institution}</span>}
              </span>
              <button
                type="button"
                aria-label={`Remove ${s.name}`}
                className="hover:bg-muted px-1"
                onClick={() => onChange(value.filter((v) => v.id !== s.id))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-muted-foreground text-[11px]">
        {value.length} of {max} selected
      </p>
    </div>
  );
}
