"use client";

import { useState } from "react";
import { useMarketAction, useMyProvider } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { formatBirr, priceBreakdown, priceRules, usePaymentsConfig, type JobPriceBody } from "@cn/core/api/payments";
import type { ClientRecord, Hire } from "@cn/core/types/provider";
import { StarInput, Stars } from "@cn/ui/marketplace/trust";

/** What the client pays and what the provider keeps for a price, worked out here from the same rules as the API. */
function PriceSplit({ job, amount }: { job: Hire; amount: number }) {
  const me = useMyProvider().data?.payload.provider;
  const config = usePaymentsConfig().data?.payload;
  const vatRegistered = me?.vat_registered ?? job.provider_vat_registered ?? false;
  const rules = priceRules(config, vatRegistered);
  const b = priceBreakdown(amount, rules);
  return (
    <p className="text-muted-foreground text-[11px]" aria-live="polite">
      Client pays <strong className="text-foreground tabular-nums">{formatBirr(b.clientPays)} ETB</strong>
      {b.vat > 0 ? ` (incl. ${formatBirr(b.vat)} VAT)` : ""} · you receive about{" "}
      <strong className="text-foreground tabular-nums">{formatBirr(b.providerGets)} ETB</strong> after the {rules.commissionPercent}% commission
      {b.commissionVat > 0 ? " and VAT on it" : ""}
      {b.vat > 0 ? "; the VAT is yours to file" : ""}.
    </p>
  );
}

/** Inline form for the price a provider names, on accept or later. */
export function PriceForm({ job, mode, onDone, onCancel }: { job: Hire; mode: "accept" | "set_price"; onDone: () => void; onCancel: () => void }) {
  const { run, isPending } = useMarketAction<JobPriceBody>();
  const [price, setPrice] = useState(job.agreed_price != null ? String(job.agreed_price) : "");
  const [note, setNote] = useState(job.price_note ?? "");
  const [error, setError] = useState<string | null>(null);
  const amount = price.trim() ? Number(price) : null;
  const badAmount = amount != null && (!Number.isFinite(amount) || amount <= 0);
  const canSubmit = !badAmount && amount != null;

  return (
    <form
      className="bg-secondary/40 space-y-2 rounded-md p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!canSubmit) return;
        setError(null);
        const priceNote = note.trim() || undefined;
        try {
          await run(
            apiPaths.providers.myJob(job.id),
            MTD.POST,
            mode === "accept"
              ? { action: "accept", ...(amount != null ? { price: amount } : {}), price_note: priceNote }
              : { action: "set_price", price: amount as number, price_note: priceNote },
          );
          onDone();
        } catch (err) {
          setError(getErrorMessage(err));
        }
      }}
    >
      <p className="text-sm font-semibold">{mode === "accept" ? "Accept this job · ተቀበል" : "Your price · ዋጋ"}</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          type="number"
          inputMode="decimal"
          min={1}
          step="any"
          aria-label="Price in birr"
          placeholder="Price in birr"
          className="sm:w-44"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        />
        <Input placeholder="Note, e.g. includes stamp fees (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <p className="text-muted-foreground text-[11px]">
        {mode === "accept" ? "You can also set or change the price later, before the client pays." : "The client sees this price and can pay it online."}
      </p>
      {amount != null && !badAmount && <PriceSplit job={job} amount={amount} />}
      {badAmount && <p className="text-destructive text-xs">Enter a price above 0.</p>}
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={!canSubmit} loading={isPending}>{mode === "accept" ? "Accept job" : "Save price"}</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

/** A client's record, so the provider can judge a request before taking it. */
export function ClientRecordLine({ record, name }: { record?: ClientRecord | null; name: string }) {
  if (!record) return null;
  const first = name.split(" ")[0];
  const parts: string[] = [];
  parts.push(record.hire_rate == null ? "New client" : `Hire rate ${record.hire_rate}%`);
  parts.push(`${record.paid_jobs} paid job${record.paid_jobs === 1 ? "" : "s"}`);
  if (record.cancelled_after_accept) parts.push(`${record.cancelled_after_accept} cancelled after acceptance`);
  if (record.left_unpaid) parts.push(`${record.left_unpaid} accepted but never paid`);
  return (
    <p className="text-muted-foreground text-xs" title="Hire rate: of the requests providers accepted, how many this client paid">
      <span className="text-foreground font-medium">{first}&apos;s record:</span> {parts.join(" · ")}
      {record.rating_count > 0 && (
        <span className="ml-1 inline-flex items-center gap-1">
          · <Stars value={record.rating_avg ?? 0} /> ({record.rating_count})
        </span>
      )}
    </p>
  );
}

export function DeliverForm({ job, onDone }: { job: Hire; onDone: () => void }) {
  const { run, isPending } = useMarketAction<{ action: string; note: string }>();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="bg-secondary/40 space-y-2 rounded-md p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        try {
          await run(apiPaths.providers.myJob(job.id), MTD.POST, { action: "complete", note: note.trim() });
          onDone();
        } catch (err) {
          setError(getErrorMessage(err));
        }
      }}
    >
      <label htmlFor={`deliver-${job.id}`} className="text-sm font-semibold">What did you deliver? · ምን አስረከቡ?</label>
      <p className="text-muted-foreground text-xs">
        {job.client_name.split(" ")[0]} sees this and confirms. For example: &quot;Passport collected from the Bole office and handed over.&quot;
      </p>
      <Textarea id={`deliver-${job.id}`} rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button size="sm" type="submit" disabled={note.trim().length < 10} loading={isPending}>
          {job.agreed_price != null ? `Mark delivered and request ${job.agreed_price.toLocaleString("en")} ETB` : "Mark delivered"}
        </Button>
        <Button size="sm" type="button" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}

export function RateClientForm({ job, onDone }: { job: Hire; onDone: () => void }) {
  const { run, isPending } = useMarketAction<{ rating: number; comment?: string }>();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const first = job.client_name.split(" ")[0];
  return (
    <div className="bg-secondary/40 space-y-2 rounded-md p-3">
      <p className="text-sm font-semibold">Rate {first} as a client · ደንበኛውን ይገምግሙ</p>
      <p className="text-muted-foreground text-xs">Clear instructions, paid on time, easy to reach? Other providers see this before taking {first}&apos;s requests. It is never public.</p>
      <StarInput value={rating} onChange={setRating} label={`Rating for ${first}`} />
      <Textarea rows={2} placeholder="Optional comment" value={comment} onChange={(e) => setComment(e.target.value)} />
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={!rating}
          loading={isPending}
          onClick={async () => {
            setError(null);
            try {
              await run(apiPaths.providers.rateClient(job.id), MTD.POST, { rating, comment: comment.trim() || undefined });
              onDone();
            } catch (err) {
              setError(getErrorMessage(err));
            }
          }}
        >
          Save rating
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </div>
  );
}
