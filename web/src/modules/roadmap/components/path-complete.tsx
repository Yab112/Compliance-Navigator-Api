"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@cn/ui/button";
import { Textarea } from "@cn/ui/textarea";
import { api } from "@cn/core/lib/api";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { StarInput } from "@cn/ui/marketplace/trust";
import type { APIResponse } from "@cn/core/types/global";
import type { Roadmap } from "@/types/roadmap";

type Feedback = { accuracy: number; days_taken: number | null; steps_different: string[]; would_recommend: boolean | null };

const DAYS = [
  { label: "Under a week", value: 5 },
  { label: "1 to 2 weeks", value: 10 },
  { label: "2 to 4 weeks", value: 21 },
  { label: "1 to 2 months", value: 45 },
  { label: "Longer", value: 90 },
];

/** Shown when every step of a path is done: congratulations, then a short "how did it go". */
export function PathComplete({ roadmap }: { roadmap: Roadmap }) {
  const qc = useQueryClient();
  const key = ["roadmaps", roadmap.id, "feedback"];
  const existing = useQuery({
    queryKey: key,
    queryFn: async () =>
      (await api.get<APIResponse<{ feedback: Feedback | null }>>(`${apiPaths.roadmaps}/${roadmap.id}/feedback`)).data.payload.feedback,
    retry: false,
  });
  const [accuracy, setAccuracy] = useState(0);
  const [days, setDays] = useState<number | null>(null);
  const [different, setDifferent] = useState<string[]>([]);
  const [what, setWhat] = useState("");
  const [recommend, setRecommend] = useState<boolean | null>(null);
  const send = useMutation({
    mutationFn: () =>
      api.post(`${apiPaths.roadmaps}/${roadmap.id}/feedback`, {
        accuracy,
        days_taken: days,
        steps_different: different,
        what_was_different: what.trim() || null,
        would_recommend: recommend,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: key }),
  });
  const offices = new Set(roadmap.steps.map((s) => s.office?.name ?? s.issuingAuthority).filter(Boolean)).size;
  const done = !!existing.data || send.isSuccess;

  return (
    <section aria-labelledby="path-done" className="border-primary/30 bg-card relative mb-8 overflow-hidden rounded-md border">
      <div className="confetti" aria-hidden>
        {Array.from({ length: 18 }, (_, i) => (
          <span key={i} style={{ left: `${(i * 53) % 100}%`, animationDelay: `${(i % 6) * 0.25}s` }} />
        ))}
      </div>
      <div className="bg-primary relative px-6 py-7 text-white">
        <p className="text-gov-yellow text-sm font-semibold">እንኳን ደስ አለዎት!</p>
        <h2 id="path-done" className="mt-1 text-2xl font-bold">
          Congratulations, you got your {roadmap.request.goalLabel}!
        </h2>
        <p className="mt-2 text-sm text-white/85">
          {roadmap.steps.length} step{roadmap.steps.length === 1 ? "" : "s"} done
          {offices ? ` across ${offices} office${offices === 1 ? "" : "s"}` : ""}. That is the whole path, finished.
        </p>
      </div>

      {done ? (
        <div className="px-6 py-6">
          <p className="font-semibold">Thank you for telling us how it went.</p>
          <p className="text-muted-foreground mt-1 text-sm">
            What you shared goes to our data team and the organizations, so the next person gets an even more accurate path.
          </p>
          <div className="mt-4 flex flex-wrap gap-2 text-sm">
            <Link href="/roadmap/new" className="bg-primary text-primary-foreground rounded-md px-4 py-2 font-semibold">
              Start another path
            </Link>
            <Link href="/account/paths" className="border-border rounded-md border px-4 py-2">
              My saved paths
            </Link>
          </div>
        </div>
      ) : (
        <form
          className="grid gap-5 px-6 py-6"
          onSubmit={(e) => {
            e.preventDefault();
            if (accuracy) send.mutate();
          }}
        >
          <div>
            <p className="font-semibold">How did it go? · እንዴት ነበር?</p>
            <p className="text-muted-foreground text-sm">One minute. It helps the next person who needs the same thing.</p>
          </div>
          <div>
            <p className="mb-1 text-sm font-medium">How accurate was the path we showed you?</p>
            <StarInput value={accuracy} onChange={setAccuracy} label="Path accuracy" />
          </div>
          <div>
            <p className="mb-1.5 text-sm font-medium">How long did it take from start to finish?</p>
            <div className="flex flex-wrap gap-1.5">
              {DAYS.map((d) => (
                <button
                  key={d.value}
                  type="button"
                  aria-pressed={days === d.value}
                  onClick={() => setDays(d.value)}
                  className={
                    days === d.value
                      ? "border-primary bg-primary text-primary-foreground rounded-full border px-3 py-1 text-sm"
                      : "border-border hover:border-primary rounded-full border px-3 py-1 text-sm"
                  }
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium">Was any step different from what we showed? Tick it.</legend>
            <ul className="grid gap-1 sm:grid-cols-2">
              {roadmap.steps.map((s) => (
                <li key={s.id}>
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="accent-primary mt-0.5 size-4"
                      checked={different.includes(s.id)}
                      onChange={() => setDifferent((x) => (x.includes(s.id) ? x.filter((v) => v !== s.id) : [...x, s.id]))}
                    />
                    {s.title}
                  </label>
                </li>
              ))}
            </ul>
            {different.length > 0 && (
              <Textarea
                className="mt-2"
                rows={3}
                placeholder="What was different? For example: the fee was 300 birr, or they also asked for a utility bill."
                value={what}
                onChange={(e) => setWhat(e.target.value)}
              />
            )}
          </fieldset>
          <div>
            <p className="mb-1.5 text-sm font-medium">Would you recommend Compliance Navigator to a friend?</p>
            <div className="flex gap-2">
              {[
                { v: true, l: "Yes" },
                { v: false, l: "No" },
              ].map((o) => (
                <Button key={o.l} type="button" size="sm" variant={recommend === o.v ? "default" : "outline"} onClick={() => setRecommend(o.v)}>
                  {o.l}
                </Button>
              ))}
            </div>
          </div>
          {send.isError && <p className="text-destructive text-sm">{getErrorMessage(send.error)}</p>}
          <div>
            <Button type="submit" disabled={!accuracy || send.isPending}>
              {send.isPending ? "Sending…" : "Send feedback"}
            </Button>
            {!accuracy && <span className="text-muted-foreground ml-3 text-xs">Pick a star rating first</span>}
          </div>
        </form>
      )}
    </section>
  );
}
