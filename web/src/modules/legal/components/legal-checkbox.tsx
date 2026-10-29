"use client";

import { LEGAL_BY_KEY, legalHref, type LegalKey } from "@/content/legal";

/** Link that opens a legal document in a new tab, so a half-filled form is not lost. */
export function LegalLink({ doc, children }: { doc: LegalKey; children?: React.ReactNode }) {
  return (
    <a href={legalHref(doc)} target="_blank" rel="noopener noreferrer" className="text-primary font-medium underline">
      {children ?? LEGAL_BY_KEY[doc].title}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

/** A required, unticked-by-default agreement box. The label holds the links to the documents. */
export function LegalCheckbox({
  id,
  checked,
  onChange,
  invalid,
  children,
}: {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  invalid?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        required
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        aria-invalid={invalid || undefined}
        className="accent-primary mt-0.5 size-5 shrink-0 cursor-pointer"
      />
      <label htmlFor={id} className="text-sm leading-relaxed">
        {children}
      </label>
    </div>
  );
}
