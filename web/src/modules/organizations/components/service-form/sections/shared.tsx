"use client";

// ---------------------------------------------------------------- sections

export function Checks<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: [T, string][];
  value: T[];
  onChange: (v: T[]) => void;
  label: string;
}) {
  return (
    <fieldset>
      <legend className="text-xs font-medium">{label}</legend>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {options.map(([v, l]) => (
          <label key={v} className="flex items-center gap-1.5">
            <input type="checkbox" checked={value.includes(v)} onChange={(e) => onChange(e.target.checked ? [...value, v] : value.filter((x) => x !== v))} />
            {l}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
