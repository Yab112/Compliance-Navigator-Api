"use client";

import { Button } from "@cn/ui/button";

export function StepActions({ onBack, backLabel = "Back", next, nextLabel = "Save and continue", pending, disabled, error }: {
  onBack: () => void;
  backLabel?: string;
  next?: () => void;
  nextLabel?: string;
  pending?: boolean;
  disabled?: boolean;
  error?: string | null;
}) {
  return (
    <div className="space-y-2 pt-2">
      {error && <p className="text-destructive text-sm">{error}</p>}
      <div className="flex flex-wrap justify-between gap-3">
        <Button type="button" variant="outline" size="lg" onClick={onBack}>
          ← {backLabel}
        </Button>
        {next && (
          <Button type="button" size="lg" loading={pending} disabled={disabled} onClick={next}>
            {nextLabel} →
          </Button>
        )}
      </div>
    </div>
  );
}

export const clean = (v: string | null | undefined) => (v && v.trim() ? v.trim() : null);
