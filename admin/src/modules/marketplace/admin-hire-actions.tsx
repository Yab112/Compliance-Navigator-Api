"use client";

import { useId, useState } from "react";
import { CANDIDATES_PAGE_SIZE, useAssignCandidates, useMarketAction } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { Pager } from "@cn/ui/pager";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { NativeSelect, useDebounced } from "@cn/ui/guday/shared";
import { AREA_OPTIONS, SPECIALTY_LABELS, areaLabel, specialtyLabel } from "@cn/ui/marketplace/constants";
import type { Hire, HireStaffAction } from "@cn/core/types/provider";

const NOTE_MIN = 5;

/** A required note with its label and error, shared by every staff action. */
function NoteField({ value, onChange, label, error }: { value: string; onChange: (v: string) => void; label: string; error?: string | null }) {
  const id = useId();
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs font-medium">{label}</label>
      <Textarea id={id} rows={2} value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined} />
      {error && <p id={`${id}-error`} role="alert" className="text-destructive text-xs">{error}</p>}
    </div>
  );
}

/** Uphold or dismiss an open complaint. Decided once; both sides are told the finding. */
export function DisputeDecision({ hire }: { hire: Hire }) {
  const { run, isPending } = useMarketAction<{ decision: string; note: string }>();
  const [note, setNote] = useState("");
  const [confirmUphold, setConfirmUphold] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const paid = hire.payment_status === "paid";
  const decide = async (decision: "upheld" | "dismissed") => {
    setError(null);
    if (note.trim().length < NOTE_MIN) {
      setError(`Write the finding first (at least ${NOTE_MIN} characters).`);
      return;
    }
    try {
      await run(apiPaths.admin.marketDispute(hire.id), MTD.POST, { decision, note: note.trim() });
      setConfirmUphold(false);
    } catch (err) {
      setError(getErrorMessage(err, "Could not save the decision"));
    }
  };
  return (
    <div className="mt-2 space-y-2 border border-amber-300 bg-amber-50 p-3 text-xs dark:bg-amber-950/30">
      <p><strong>Complaint:</strong> {hire.dispute_reason}</p>
      <NoteField label="Finding (the client and the provider are both told)" value={note} onChange={setNote} error={error} />
      {confirmUphold ? (
        <div className="space-y-2">
          <p>
            Upholding takes 10 trust points from the provider.
            {paid && " This job is paid, so it will also be marked as needing a refund."} Continue?
          </p>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="destructive" loading={isPending} onClick={() => decide("upheld")}>Yes, uphold</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirmUphold(false)}>Go back</Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="destructive" disabled={isPending} onClick={() => setConfirmUphold(true)}>
            Uphold (minus 10 trust points)
          </Button>
          <Button size="sm" variant="outline" loading={isPending} onClick={() => decide("dismissed")}>Dismiss</Button>
        </div>
      )}
    </div>
  );
}

/** Search and pick a listed provider who is taking work, best fit for this request first. */
export function AssignProvider({ hire, onDone }: { hire: Hire; onDone?: () => void }) {
  const [query, setQuery] = useState("");
  const q = useDebounced(query.trim(), 300);
  const [area, setArea] = useState(hire.sub_city ?? "");
  const [specialty, setSpecialty] = useState(hire.specialty ?? "");
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(CANDIDATES_PAGE_SIZE);
  const [pick, setPick] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading, isError } = useAssignCandidates(hire.id, { q, area, specialty, page, size });
  const { run, isPending } = useMarketAction<{ action: "assign"; provider_id: string; note: string }>();
  const items = data?.payload.items ?? [];
  const searchId = useId();
  const listName = useId();

  const assign = async () => {
    setError(null);
    if (!pick) return setError("Choose a provider.");
    if (note.trim().length < NOTE_MIN) return setError(`Write why (at least ${NOTE_MIN} characters).`);
    try {
      await run(apiPaths.admin.marketHire(hire.id), MTD.PATCH, { action: "assign", provider_id: pick, note: note.trim() });
      setPick(null);
      setNote("");
      onDone?.();
    } catch (err) {
      setError(getErrorMessage(err, "Could not assign"));
    }
  };

  return (
    <div className="space-y-2 text-xs">
      <div className="grid gap-2 sm:grid-cols-3">
        <div className="space-y-1">
          <label htmlFor={searchId} className="font-medium">Search</label>
          <Input id={searchId} placeholder="Name, registration no. or phone" value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(0); }} />
        </div>
        <label className="space-y-1">
          <span className="font-medium">Area</span>
          <NativeSelect value={area} onChange={(e) => { setArea(e.target.value); setPage(0); }}>
            <option value="">Any area</option>
            {AREA_OPTIONS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </NativeSelect>
        </label>
        <label className="space-y-1">
          <span className="font-medium">Specialty</span>
          <NativeSelect value={specialty} onChange={(e) => { setSpecialty(e.target.value); setPage(0); }}>
            <option value="">Any specialty</option>
            {Object.keys(SPECIALTY_LABELS).map((k) => <option key={k} value={k}>{specialtyLabel(k, true)}</option>)}
          </NativeSelect>
        </label>
      </div>
      <p className="text-muted-foreground">
        Only approved providers with a valid licence who are taking work. Best fit first: the requested service, then
        specialty, then area, then trust score.
      </p>
      {isLoading ? (
        <p className="text-muted-foreground">Loading providers…</p>
      ) : isError ? (
        <p className="text-destructive">Could not load providers.</p>
      ) : !items.length ? (
        <p className="text-muted-foreground">No provider matches. Try another area or clear the specialty.</p>
      ) : (
        <fieldset>
          <legend className="sr-only">Choose a provider</legend>
          <ul className="divide-border border-border divide-y border">
            {items.map((c) => (
              <li key={c.id}>
                <label className={cn("flex cursor-pointer items-start gap-2 p-2", pick === c.id && "bg-secondary")}>
                  <input type="radio" name={listName} className="accent-primary mt-0.5" checked={pick === c.id} onChange={() => setPick(c.id)} />
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{c.display_name}</span>
                    <span className="text-muted-foreground"> · {c.registration_no ?? "no reg. no."} · score {c.trust_score}</span>
                    <span className="text-muted-foreground block">
                      {[c.sub_city ? areaLabel(c.sub_city) : null, `${c.completed_count} done`, `${c.open_jobs} open`].filter(Boolean).join(" · ")}
                    </span>
                    <span className="mt-0.5 flex flex-wrap gap-1">
                      {c.offers_service && <Tag>Offers this service</Tag>}
                      {c.same_specialty && <Tag>Same specialty</Tag>}
                      {c.covers_area && <Tag>Covers the area</Tag>}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      )}
      <Pager
        page={page}
        pageSize={size}
        total={data?.payload.total ?? 0}
        onPage={setPage}
        onPageSize={(n) => { setSize(n); setPage(0); }}
        className="mt-2"
      />
      <NoteField label="Why this provider (staff only)" value={note} onChange={setNote} error={error} />
      <p className="text-muted-foreground">The provider gets the request and sees the client&apos;s phone only after they accept.</p>
      <Button size="sm" disabled={!pick} loading={isPending} onClick={assign}>Assign</Button>
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return <span className="rounded bg-emerald-100 px-1 text-[10px] text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">{children}</span>;
}

const ACTION_COPY: Record<Exclude<HireStaffAction, "assign">, { label: string; confirm: string; variant: "destructive" | "outline" }> = {
  cancel: { label: "Cancel the request", confirm: "Cancel this request? The client and the provider are told.", variant: "destructive" },
  reopen: { label: "Reopen for a new provider", confirm: "Send this request back to the staff queue with no provider?", variant: "outline" },
  note: { label: "Add a staff note", confirm: "Save this note to the history?", variant: "outline" },
};

/** Cancel, reopen or note: each needs a written reason and is kept in the hire's history. */
export function StaffChange({ hire, action }: { hire: Hire; action: Exclude<HireStaffAction, "assign"> }) {
  const { run, isPending } = useMarketAction<{ action: string; note: string }>();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const copy = ACTION_COPY[action];
  const save = async () => {
    setError(null);
    if (note.trim().length < NOTE_MIN) return setError(`Write why (at least ${NOTE_MIN} characters).`);
    try {
      await run(apiPaths.admin.marketHire(hire.id), MTD.PATCH, { action, note: note.trim() });
      setOpen(false);
      setNote("");
    } catch (err) {
      setError(getErrorMessage(err, "Could not save"));
    }
  };
  if (!open) {
    return <Button size="sm" variant="outline" onClick={() => setOpen(true)}>{copy.label}</Button>;
  }
  return (
    <div className="border-border w-full space-y-2 border p-3 text-xs">
      <NoteField label={action === "note" ? "Note (staff only)" : "Reason (staff only)"} value={note} onChange={setNote} error={error} />
      <p>{copy.confirm}</p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={copy.variant} loading={isPending} onClick={save}>{action === "note" ? "Save note" : `Yes, ${copy.label.toLowerCase()}`}</Button>
        <Button size="sm" variant="ghost" onClick={() => { setOpen(false); setError(null); }}>Close</Button>
      </div>
    </div>
  );
}
