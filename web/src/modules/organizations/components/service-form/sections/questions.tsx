"use client";

import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { Field, NativeSelect } from "@cn/ui/guday/shared";
import { type Question, type Requirement, type Rule } from "@cn/core/types/organizations";
import { toKey, lines, type SectionProps } from "@/modules/organizations/components/service-form/model";

function RuleEditor({ q, rule, conditional, onChange, onRemove }: { q: Question; rule: Rule; conditional: Requirement[]; onChange: (patch: Partial<Rule>) => void; onRemove: () => void }) {
  return (
    <div className="bg-secondary/40 grid gap-2 rounded-md p-3 text-sm sm:grid-cols-[auto_1fr]">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">If the answer is</span>
        {q.type === "number" && (
          <NativeSelect aria-label="Comparison" className="h-8 w-20" value={rule.op} onChange={(e) => onChange({ op: e.target.value as Rule["op"] })}>
            <option value="eq">=</option>
            <option value="gt">&gt;</option>
            <option value="gte">≥</option>
            <option value="lt">&lt;</option>
            <option value="lte">≤</option>
          </NativeSelect>
        )}
        {q.type === "yes_no" ? (
          <NativeSelect aria-label="Answer" className="h-8 w-24" value={rule.value} onChange={(e) => onChange({ value: e.target.value })}>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </NativeSelect>
        ) : q.type === "single_choice" ? (
          <NativeSelect aria-label="Answer" className="h-8 w-40" value={rule.value} onChange={(e) => onChange({ value: e.target.value })}>
            <option value="">Choose</option>
            {q.options.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </NativeSelect>
        ) : (
          <Input aria-label="Answer" className="h-8 w-32" value={rule.value} onChange={(e) => onChange({ value: e.target.value })} />
        )}
      </div>
      <div className="space-y-2">
        {conditional.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <span className="text-muted-foreground">add:</span>
            {conditional.map((r) => (
              <label key={r.key} className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={rule.add_requirements.includes(r.key)}
                  onChange={(e) => onChange({ add_requirements: e.target.checked ? [...rule.add_requirements, r.key] : rule.add_requirements.filter((k) => k !== r.key) })}
                />
                {r.name || r.key}
              </label>
            ))}
          </div>
        )}
        <Input aria-label="Not eligible reason" className="h-8" placeholder="Or stop here: why the person can't apply (optional)" value={rule.ineligible ?? ""} onChange={(e) => onChange({ ineligible: e.target.value })} />
        <button type="button" className="text-destructive text-xs" onClick={onRemove}>
          Remove rule
        </button>
      </div>
    </div>
  );
}

export function QuestionsSection({ form, set }: SectionProps) {
  const conditional = form.requirements.filter((r) => r.required === "conditional");
  const update = (i: number, patch: Partial<Question>) => set({ questions: form.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)) });
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground text-sm">
        Ask what decides which documents apply, for example &quot;Are you renting the premises?&quot;. Each answer can add documents marked
        &quot;Only in some cases&quot; or tell people they can&apos;t apply. Skip this section if the list is the same for everyone.
      </p>
      <ol className="space-y-4">
        {form.questions.map((q, i) => (
          <li key={i} className="border-border space-y-3 rounded-md border p-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_1fr_180px]">
              <Field label={`Question ${i + 1}`} htmlFor={`q-${i}`} required>
                <Input id={`q-${i}`} value={q.prompt} onChange={(e) => update(i, { prompt: e.target.value })} />
              </Field>
              <Field label="ጥያቄ (Amharic)" htmlFor={`q-am-${i}`}>
                <Input id={`q-am-${i}`} value={q.prompt_am ?? ""} onChange={(e) => update(i, { prompt_am: e.target.value })} />
              </Field>
              <Field label="Answer type" htmlFor={`q-type-${i}`}>
                <NativeSelect id={`q-type-${i}`} className="h-9" value={q.type} onChange={(e) => update(i, { type: e.target.value as Question["type"], rules: [] })}>
                  <option value="yes_no">Yes / No</option>
                  <option value="single_choice">One of several</option>
                  <option value="number">Number</option>
                  <option value="text">Text</option>
                </NativeSelect>
              </Field>
            </div>
            {q.type === "single_choice" && (
              <Field label="Choices (one per line)" htmlFor={`q-opt-${i}`}>
                <Textarea id={`q-opt-${i}`} rows={3} value={q.options.join("\n")} onChange={(e) => update(i, { options: lines(e.target.value) })} />
              </Field>
            )}
            {q.rules.map((rule, ri) => (
              <RuleEditor
                key={ri}
                q={q}
                rule={rule}
                conditional={conditional}
                onChange={(patch) => update(i, { rules: q.rules.map((r, k) => (k === ri ? { ...r, ...patch } : r)) })}
                onRemove={() => update(i, { rules: q.rules.filter((_, k) => k !== ri) })}
              />
            ))}
            <div className="flex justify-between">
              <button
                type="button"
                className="text-primary text-xs font-medium"
                onClick={() => update(i, { rules: [...q.rules, { op: "eq", value: q.type === "yes_no" ? "yes" : (q.options[0] ?? ""), add_requirements: [], ineligible: "" }] })}
              >
                + Add a rule for an answer
              </button>
              <button type="button" className="text-destructive text-xs" onClick={() => set({ questions: form.questions.filter((_, j) => j !== i) })}>
                Remove question
              </button>
            </div>
          </li>
        ))}
      </ol>
      <Button
        type="button"
        variant="outline"
        onClick={() =>
          set({
            questions: [
              ...form.questions,
              { key: toKey(`q ${form.questions.length + 1}`, form.questions.map((q) => q.key)), prompt: "", prompt_am: "", type: "yes_no", options: [], rules: [] },
            ],
          })
        }
      >
        + Add a question
      </Button>
    </div>
  );
}
