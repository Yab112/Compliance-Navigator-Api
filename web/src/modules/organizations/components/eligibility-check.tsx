"use client";

import Link from "next/link";
import { useState } from "react";
import { useEligibility } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { APPLIES_TO_LABEL } from "@cn/core/types/organizations";
import type { PublicRequirement, PublicService } from "@cn/core/types/organizations";
import { PathFlow } from "@/modules/organizations/components/path-flow";

type Answers = Record<string, string | number | boolean | null>;

/** Readable "issued in the last 3 months" from a day count. */
function maxAge(days: number): string {
  if (days % 365 === 0) return `${days / 365} year${days === 365 ? "" : "s"}`;
  if (days % 30 === 0) return `${days / 30} month${days === 30 ? "" : "s"}`;
  return `${days} days`;
}

export function RequirementItem({ req }: { req: PublicRequirement }) {
  const extra = [
    req.original_or_copy === "original" && "original",
    req.original_or_copy === "copy" && "copy",
    req.original_or_copy === "both" && "original and a copy",
    req.copies && `${req.copies} cop${req.copies === 1 ? "y" : "ies"}`,
    req.applies_to && req.applies_to !== "applicant" && `from ${APPLIES_TO_LABEL[req.applies_to]}`,
  ].filter(Boolean);
  const tags = [
    req.notarized && "Must be notarized",
    req.translated && "Needs an Amharic translation",
    req.max_age_days && `Issued in the last ${maxAge(req.max_age_days)}`,
  ].filter(Boolean) as string[];
  return (
    <li className="border-border flex gap-3 border-b py-3 last:border-0">
      <span className="text-primary mt-0.5" aria-hidden>
        ☐
      </span>
      <div className="min-w-0">
        <p className="font-medium">
          {req.name}
          {extra.length > 0 && <span className="text-muted-foreground text-sm font-normal"> ({extra.join(", ")})</span>}
        </p>
        {tags.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {tags.map((t) => (
              <span key={t} className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-900">
                {t}
              </span>
            ))}
          </div>
        )}
        {req.photo_specs && <p className="mt-1 text-sm">Photo: {req.photo_specs}</p>}
        {req.issued_by && (
          <p className="text-sm">
            Get it from{" "}
            <Link
              href={`/organizations/${req.issued_by.org_slug}/services/${req.issued_by.service_slug}`}
              className="text-primary font-medium hover:underline"
            >
              {req.issued_by.service_name}
            </Link>{" "}
            at{" "}
            <Link href={`/organizations/${req.issued_by.org_slug}`} className="hover:underline">
              {req.issued_by.org_name}
            </Link>
          </p>
        )}
        {(req.alternatives?.length ?? 0) > 0 && (
          <p className="text-muted-foreground mt-1 text-sm">Also accepted: {req.alternatives!.join("; ")}</p>
        )}
        {req.notes && <p className="text-muted-foreground mt-1 text-sm">{req.notes}</p>}
      </div>
    </li>
  );
}

/** Answer the organization's questions and get the exact checklist and path for your case. */
export function EligibilityCheck({ service }: { service: PublicService }) {
  const check = useEligibility(service.id);
  const [answers, setAnswers] = useState<Answers>({});
  const set = (key: string, value: string | number | boolean | null) => setAnswers((a) => ({ ...a, [key]: value }));
  const result = check.data;

  if (!service.questions.length) return null;

  return (
    <div>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          check.mutate(answers);
        }}
      >
        {service.questions.map((q, i) => (
          <fieldset key={q.key} className="border-border rounded-md border p-4">
            <legend className="px-1 text-sm font-medium">
              {i + 1}. {q.prompt}
              {q.prompt_am && <span className="text-muted-foreground font-normal"> · {q.prompt_am}</span>}
            </legend>
            {q.type === "yes_no" && (
              <div className="mt-2 flex gap-2">
                {["yes", "no"].map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => set(q.key, v)}
                    aria-pressed={answers[q.key] === v}
                    className={cn(
                      "rounded-md border px-4 py-1.5 text-sm",
                      answers[q.key] === v ? "border-primary bg-primary text-white" : "border-border hover:border-primary",
                    )}
                  >
                    {v === "yes" ? "Yes · አዎ" : "No · አይ"}
                  </button>
                ))}
              </div>
            )}
            {q.type === "single_choice" && (
              <div className="mt-2 flex flex-wrap gap-2">
                {q.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => set(q.key, opt)}
                    aria-pressed={answers[q.key] === opt}
                    className={cn(
                      "rounded-md border px-3 py-1.5 text-sm",
                      answers[q.key] === opt ? "border-primary bg-primary text-white" : "border-border hover:border-primary",
                    )}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
            {(q.type === "number" || q.type === "text") && (
              <Input
                className="mt-2 max-w-xs"
                type={q.type === "number" ? "number" : "text"}
                value={(answers[q.key] as string | number | undefined) ?? ""}
                onChange={(e) => set(q.key, q.type === "number" && e.target.value !== "" ? Number(e.target.value) : e.target.value)}
              />
            )}
          </fieldset>
        ))}
        <Button type="submit" size="lg" loading={check.isPending}>
          Show what I need
        </Button>
        {check.isError && <p className="text-destructive text-sm">{getErrorMessage(check.error)}</p>}
      </form>

      {result && (
        <div className="mt-6 space-y-6" aria-live="polite">
          {!result.eligible ? (
            <div className="border-destructive/30 bg-destructive/5 rounded-md border p-4">
              <p className="text-destructive font-semibold">Based on your answers you can’t apply for this service yet.</p>
              <ul className="mt-2 list-disc pl-5 text-sm">
                {result.ineligible_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          ) : (
            <>
              <div>
                <h3 className="text-gov-ink font-semibold">Your checklist · የሚያስፈልጉዎት</h3>
                {result.unanswered.length > 0 && (
                  <p className="text-muted-foreground text-xs">
                    Answer every question for a complete list. Unanswered questions may add documents.
                  </p>
                )}
                <ul className="mt-2">
                  {result.checklist.map((r) => (
                    <RequirementItem key={r.key} req={r} />
                  ))}
                </ul>
              </div>
              {result.path && result.path.steps.length > 1 && (
                <div>
                  <h3 className="text-gov-ink mb-3 font-semibold">Your path across organizations · የእርስዎ መንገድ</h3>
                  <PathFlow path={result.path} />
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
