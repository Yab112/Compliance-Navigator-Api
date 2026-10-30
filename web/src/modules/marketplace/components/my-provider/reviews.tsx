"use client";

import { useState } from "react";
import { MY_REVIEWS_PAGE_SIZE, useMarketAction, useMyProviderReviews } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { LoadingState } from "@cn/ui/guday/shared";
import type { MyProvider, Review } from "@cn/core/types/provider";
import { RatingSummary } from "@cn/ui/marketplace/trust";
import { ReviewItem } from "@/modules/marketplace/pages/provider-profile";
import { Card } from "@/modules/marketplace/components/my-provider/shared";

function ReplyBox({ review }: { review: Review }) {
  const { run, isPending } = useMarketAction<{ reply: string }>();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  if (review.reply) return null;
  return (
    <div className="mb-4 flex flex-col gap-2 sm:flex-row">
      <Textarea rows={2} placeholder="Public reply (once)" value={text} onChange={(e) => setText(e.target.value)} />
      <Button
        size="sm"
        disabled={text.trim().length < 2}
        loading={isPending}
        onClick={async () => {
          setError(null);
          try {
            await run(apiPaths.providers.reply(review.id), MTD.POST, { reply: text.trim() });
          } catch (err) {
            setError(getErrorMessage(err));
          }
        }}
      >
        Reply
      </Button>
      {error && <p className="text-destructive text-xs">{error}</p>}
    </div>
  );
}

export function Reviews({ p }: { p: MyProvider }) {
  const [page, setPage] = useUrlPage();
  const { data, isLoading } = useMyProviderReviews(page);
  if (isLoading) return <LoadingState />;
  const items = data?.payload.items ?? [];
  return (
    <Card>
      <div className="mb-4"><RatingSummary value={p.rating_avg} count={p.rating_count} /></div>
      {!items.length ? (
        <p className="text-muted-foreground text-sm">No reviews yet. Clients can review you after a job is completed.</p>
      ) : (
        <ul>
          {items.map((r) => (
            <div key={r.id}>
              <ReviewItem review={r} providerName={p.display_name} providerPhoto={p.photo_url} providerEntity={p.entity_type} />
              <ReplyBox review={r} />
            </div>
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={MY_REVIEWS_PAGE_SIZE} total={data?.payload.total ?? 0} onPage={setPage} />
    </Card>
  );
}
