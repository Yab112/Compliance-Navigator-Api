"use client";

import Link from "next/link";
import { useState } from "react";
import { CONSENTS_PAGE_SIZE, useMyConsents } from "@cn/core/api/legal";
import { Pager } from "@cn/ui/pager";
import { formatDateTime } from "@cn/ui/guday/shared";

/** Account page: every version of our documents this person accepted, and when. */
export function MyAgreements() {
  const [page, setPage] = useState(0);
  const consents = useMyConsents(page);
  const items = consents.data?.payload.items ?? [];

  return (
    <div>
      <p className="text-muted-foreground mb-4 text-sm">
        What you agreed to and when. Read the current versions any time on the{" "}
        <Link href="/legal" className="text-primary underline">
          legal page
        </Link>
        .
      </p>
      {consents.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : consents.isError ? (
        <p role="alert" className="text-destructive text-sm">Could not load your agreements. Try again later.</p>
      ) : items.length === 0 ? (
        <p className="text-muted-foreground text-sm">No agreements on record yet.</p>
      ) : (
        <ul className="border-border divide-y rounded-md border">
          {items.map((c) => (
            <li key={`${c.document}-${c.version}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3 text-sm">
              <span className="min-w-0">
                {c.path ? (
                  <Link href={c.path} className="text-primary font-medium hover:underline">
                    {c.title}
                  </Link>
                ) : (
                  <span className="font-medium">{c.title}</span>
                )}{" "}
                <span className="text-muted-foreground">
                  version {c.version}
                  {!c.current && " (older version)"}
                </span>
              </span>
              <span className="text-muted-foreground text-xs">Accepted {formatDateTime(c.acceptedAt)}</span>
            </li>
          ))}
        </ul>
      )}
      <Pager className="mt-4" page={page} pageSize={CONSENTS_PAGE_SIZE} total={consents.data?.payload.total ?? 0} onPage={setPage} />
    </div>
  );
}
