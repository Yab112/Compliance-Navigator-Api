"use client";

import { useState } from "react";
import { useMarketAction } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { StarInput, Stars } from "@cn/ui/marketplace/trust";
import { SUB_RATINGS } from "@cn/ui/marketplace/constants";
import type { Hire, ReviewInput } from "@cn/core/types/provider";

export function ReviewForm({ hire, onDone }: { hire: Hire; onDone: () => void }) {
  const { run, isPending } = useMarketAction<ReviewInput>();
  const [rating, setRating] = useState(0);
  const [subs, setSubs] = useState<Record<string, number>>({});
  const [again, setAgain] = useState<boolean | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="bg-secondary/40 mt-3 space-y-3 rounded-md p-4">
      <p className="text-sm font-semibold">Review {hire.provider_name} · ግምገማ</p>
      <div className="flex items-center gap-3">
        <span className="w-28 text-xs font-medium">Overall</span>
        <StarInput value={rating} onChange={setRating} label="Overall rating" />
      </div>
      {SUB_RATINGS.map((s) => (
        <div key={s.key} className="flex items-center gap-3">
          <span className="w-28 text-xs">{s.label}</span>
          <StarInput size="sm" value={subs[s.key] ?? 0} onChange={(v) => setSubs((x) => ({ ...x, [s.key]: v }))} label={s.label} />
        </div>
      ))}
      <fieldset className="flex items-center gap-4 text-xs">
        <legend className="sr-only">Would you hire again?</legend>
        <span className="w-28 font-medium">Hire again?</span>
        {[{ v: true, l: "Yes" }, { v: false, l: "No" }].map((o) => (
          <label key={o.l} className="flex items-center gap-1.5">
            <input type="radio" name={`again-${hire.id}`} className="accent-primary" checked={again === o.v} onChange={() => setAgain(o.v)} />
            {o.l}
          </label>
        ))}
      </fieldset>
      <Textarea rows={3} placeholder="What went well, what didn't? Your first name and initial are shown." value={comment} onChange={(e) => setComment(e.target.value)} />
      {error && <p className="text-destructive text-xs">{error}</p>}
      <Button
        size="sm"
        disabled={!rating}
        loading={isPending}
        onClick={async () => {
          setError(null);
          try {
            await run(apiPaths.hires.review(hire.id), MTD.POST, {
              rating,
              ...subs,
              would_hire_again: again ?? undefined,
              comment: comment.trim() || undefined,
            });
            onDone();
          } catch (err) {
            setError(getErrorMessage(err, "Could not save your review"));
          }
        }}
      >
        Publish review
      </Button>
    </div>
  );
}

type ChangeBody = { rating: number; comment?: string; reason: string };

/** Ask to change a published review. Staff approve it before it appears; nothing changes until then. */
export function ReviewChangeForm({ hire, onDone }: { hire: Hire; onDone: () => void }) {
  const { run, isPending } = useMarketAction<ChangeBody>();
  const [rating, setRating] = useState(hire.review_rating ?? 0);
  const [comment, setComment] = useState(hire.review_comment ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const unchanged = rating === (hire.review_rating ?? 0) && comment.trim() === (hire.review_comment ?? "").trim();
  const commentId = `change-comment-${hire.id}`;
  const reasonId = `change-reason-${hire.id}`;

  return (
    <div className="bg-secondary/40 mt-3 space-y-3 rounded-md p-4">
      <div>
        <p className="text-sm font-semibold">Request a change to your review</p>
        <p className="text-muted-foreground text-xs">Our team reviews changes before they appear. Until then your review stays as it is.</p>
      </div>
      <div className="flex items-center gap-3">
        <span className="w-28 text-xs font-medium">Rating</span>
        <StarInput value={rating} onChange={setRating} label="New rating" />
      </div>
      <div className="space-y-1">
        <label htmlFor={commentId} className="text-xs font-medium">Comment</label>
        <Textarea id={commentId} rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
      </div>
      <div className="space-y-1">
        <label htmlFor={reasonId} className="text-xs font-medium">Why do you want to change it?</label>
        <Textarea id={reasonId} rows={2} placeholder="For example: the provider fixed the problem afterwards." value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      {unchanged && rating > 0 && <p className="text-muted-foreground text-xs">Change the rating or the comment to send a request.</p>}
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={!rating || unchanged || reason.trim().length < 5}
          loading={isPending}
          onClick={async () => {
            setError(null);
            try {
              await run(apiPaths.hires.reviewChange(hire.id), MTD.POST, {
                rating,
                comment: comment.trim() || undefined,
                reason: reason.trim(),
              });
              onDone();
            } catch (err) {
              setError(getErrorMessage(err, "Could not send your request"));
            }
          }}
        >
          Send for review
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </div>
  );
}

/** On closed jobs: how the provider rated the client, and the client's own review with its reply. */
export function ClosedJobFeedback({ hire, changing, onRequestChange }: { hire: Hire; changing: boolean; onRequestChange: () => void }) {
  const who = hire.provider_name?.split(" ")[0] ?? "The provider";
  if (!hire.client_rating && !hire.review_rating) return null;
  return (
    <div className="mt-3 space-y-3 text-sm">
      {hire.client_rating ? (
        <div>
          <p className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="font-medium">{who} rated you</span>
            <Stars value={hire.client_rating} />
          </p>
          {hire.client_rating_comment && <p className="text-muted-foreground mt-0.5 text-xs">&ldquo;{hire.client_rating_comment}&rdquo;</p>}
        </div>
      ) : null}
      {hire.review_rating ? (
        <div className="border-border rounded-md border p-3">
          <p className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="font-medium">Your review</span>
            <Stars value={hire.review_rating} />
            {hire.review_edited_at && <span className="text-muted-foreground">· edited</span>}
          </p>
          {hire.review_comment && <p className="mt-1 text-sm">{hire.review_comment}</p>}
          {hire.review_reply && (
            <div className="bg-secondary/40 mt-2 rounded-md px-3 py-1.5 text-xs">
              <p className="font-medium">{who} replied</p>
              <p className="text-muted-foreground mt-0.5">{hire.review_reply}</p>
            </div>
          )}
          {hire.review_change_status === "pending" ? (
            <p className="text-muted-foreground mt-2 text-xs">Change requested · waiting for our team</p>
          ) : (
            <>
              {/* A rejection isn't final: new facts (e.g. the document arrived after all) can justify a new request */}
              {hire.review_change_status === "rejected" && (
                <p className="text-muted-foreground mt-2 text-xs">Your last change request was not approved.</p>
              )}
              {!changing && (
                <Button size="sm" variant="ghost" className="mt-2 -ml-2" onClick={onRequestChange}>
                  Request a change
                </Button>
              )}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
