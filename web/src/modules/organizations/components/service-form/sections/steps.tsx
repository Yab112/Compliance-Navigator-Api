"use client";

import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Field } from "@cn/ui/guday/shared";
import { type Step } from "@cn/core/types/organizations";
import { num, type SectionProps } from "@/modules/organizations/components/service-form/model";

export function StepsSection({ form, set }: SectionProps) {
  const update = (i: number, patch: Partial<Step>) => set({ steps: form.steps.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-sm">What happens at the office, in order, so people know which window to go to next.</p>
      <ol className="space-y-3">
        {form.steps.map((s, i) => (
          <li key={i} className="border-border grid gap-3 rounded-md border p-4 sm:grid-cols-[1fr_200px_140px_auto]">
            <Field label={`Step ${i + 1}`} htmlFor={`st-${i}`} required>
              <Input id={`st-${i}`} value={s.title} onChange={(e) => update(i, { title: e.target.value })} placeholder="e.g. Pay the fee" />
            </Field>
            <Field label="Where" htmlFor={`st-loc-${i}`}>
              <Input id={`st-loc-${i}`} value={s.location ?? ""} onChange={(e) => update(i, { location: e.target.value })} placeholder="Window 2" />
            </Field>
            <Field label="Minutes" htmlFor={`st-min-${i}`}>
              <Input id={`st-min-${i}`} type="number" min={0} value={s.estimated_minutes ?? ""} onChange={(e) => update(i, { estimated_minutes: num(e.target.value) })} />
            </Field>
            <div className="flex items-end gap-1">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={i === 0}
                aria-label="Move up"
                onClick={() => {
                  const next = [...form.steps];
                  [next[i - 1], next[i]] = [next[i], next[i - 1]];
                  set({ steps: next });
                }}
              >
                ↑
              </Button>
              <Button type="button" size="sm" variant="ghost" aria-label="Remove step" onClick={() => set({ steps: form.steps.filter((_, j) => j !== i) })}>
                ✕
              </Button>
            </div>
            <Field label="Details" htmlFor={`st-desc-${i}`} className="sm:col-span-4">
              <Input id={`st-desc-${i}`} value={s.description ?? ""} onChange={(e) => update(i, { description: e.target.value })} />
            </Field>
          </li>
        ))}
      </ol>
      <Button type="button" variant="outline" onClick={() => set({ steps: [...form.steps, { title: "", location: "", description: "", estimated_minutes: null }] })}>
        + Add a step
      </Button>
    </div>
  );
}
