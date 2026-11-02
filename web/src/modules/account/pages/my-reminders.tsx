"use client";

import Link from "next/link";
import { useState } from "react";
import { useAddReminder, useCancelReminder, useReminders } from "@/api/reminders";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { getErrorMessage } from "@cn/core/lib/errors";
import { EmptyState, ErrorState, LoadingState } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";

const day = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

/** /account/reminders: reminders set from the assistant or here; they arrive under the bell on the day. */
export function MyReminders() {
  const gate = useAuthGate();
  const { data, isLoading, isError, error, refetch } = useReminders();
  const add = useAddReminder();
  const cancel = useCancelReminder();
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const items = data?.items ?? [];
  const upcoming = items.filter((r) => !r.delivered_at);
  const past = items.filter((r) => r.delivered_at);

  return (
    <PageShell
      title="My reminders · አስታዋሾቼ"
      description="Deadlines and follow-ups you asked to be reminded of. Each one appears under your bell on its day."
      maxWidth="lg"
    >
      <form
        className="border-border bg-card mb-5 flex flex-wrap items-end gap-2 rounded-md border p-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setFormError(null);
          try {
            await add.mutateAsync({ title: title.trim(), due_on: due });
            setTitle("");
            setDue("");
          } catch (err) {
            setFormError(getErrorMessage(err, "Couldn't save the reminder"));
          }
        }}
      >
        <label className="grid min-w-0 flex-1 gap-1 text-xs">
          <span className="text-muted-foreground">Remind me to</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            minLength={3}
            maxLength={200}
            placeholder="Renew my trade licence"
            className="border-input bg-background h-9 rounded-md border px-2 text-sm"
          />
        </label>
        <label className="grid gap-1 text-xs">
          <span className="text-muted-foreground">On</span>
          <input
            type="date"
            value={due}
            onChange={(e) => setDue(e.target.value)}
            required
            className="border-input bg-background h-9 rounded-md border px-2 text-sm"
          />
        </label>
        <Button type="submit" loading={add.isPending}>
          Add reminder
        </Button>
        {formError && (
          <p role="alert" className="text-destructive w-full text-xs">
            {formError}
          </p>
        )}
      </form>

      {gate === "loading" || isLoading ? (
        <LoadingState label="Loading your reminders…" />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load your reminders"} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title="No reminders yet">
          <p>Ask the assistant to remind you of a deadline, or add one above.</p>
        </EmptyState>
      ) : (
        <>
          <ul className="grid gap-2">
            {upcoming.map((r) => (
              <li key={r.id} className="border-border bg-card flex flex-wrap items-center gap-3 rounded-md border p-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{r.title}</p>
                  <p className="text-muted-foreground text-xs">
                    {day(r.due_on)}
                    {r.source === "assistant" ? " · set from the assistant" : ""}
                    {r.link && (
                      <>
                        {" · "}
                        <Link href={r.link} className="text-primary hover:underline">
                          open
                        </Link>
                      </>
                    )}
                  </p>
                </div>
                <Button size="sm" variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate(r.id)}>
                  Cancel
                </Button>
              </li>
            ))}
          </ul>
          {past.length > 0 && (
            <>
              <h2 className="text-muted-foreground mt-6 mb-2 text-xs font-semibold tracking-wide uppercase">Already sent</h2>
              <ul className="grid gap-1 text-sm">
                {past.map((r) => (
                  <li key={r.id} className="text-muted-foreground">
                    {r.title} · {day(r.due_on)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </PageShell>
  );
}
