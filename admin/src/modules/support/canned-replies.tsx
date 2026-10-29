"use client";

import Link from "next/link";
import { useState } from "react";
import { CANNED_PAGE_SIZE, useCannedReplies, useCannedReplyAdmin } from "@cn/core/api/support";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { Field, useDebounced } from "@cn/ui/guday/shared";
import { getErrorMessage } from "@cn/core/lib/errors";
import { timeAgo } from "@cn/core/lib/format";
import { AdminPage } from "@/modules/components/admin-page";
import { NativeSelect } from "@/modules/shared/native-select";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { QUEUE_LABELS, type CannedReply, type SupportQueue } from "@cn/core/types/support";

type Draft = { id?: string; title: string; body: string; queue: SupportQueue | "" };
const EMPTY: Draft = { title: "", body: "", queue: "" };

function Editor({
  draft,
  placeholders,
  onDone,
}: {
  draft: Draft;
  placeholders: Record<string, string>;
  onDone: () => void;
}) {
  const { create, update, isPending } = useCannedReplyAdmin();
  const [v, setV] = useState(draft);
  const [errors, setErrors] = useState<{ title?: string; body?: string }>({});
  const [failure, setFailure] = useState<string | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const next: typeof errors = {};
    if (v.title.trim().length < 3) next.title = "Give it a short title (at least 3 characters)";
    if (!v.body.trim()) next.body = "Write the reply text";
    setErrors(next);
    if (next.title || next.body) return;
    setFailure(null);
    const body = { title: v.title.trim(), body: v.body.trim(), queue: v.queue || null };
    try {
      if (v.id) await update(v.id, body);
      else await create(body);
      onDone();
    } catch (err) {
      setFailure(getErrorMessage(err, "The reply was not saved."));
    }
  };

  const insert = (key: string) => setV((x) => ({ ...x, body: `${x.body}{{${key}}}` }));

  return (
    <form onSubmit={save} noValidate className="border-border bg-card mb-6 space-y-3 border p-4">
      <h2 className="text-sm font-semibold">{v.id ? "Edit saved reply" : "New saved reply"}</h2>
      <div className="grid gap-3 sm:grid-cols-[1fr_16rem]">
        <Field label="Title" htmlFor="cr-title" required error={errors.title} hint="Staff pick replies by this title">
          <Input
            id="cr-title"
            value={v.title}
            maxLength={120}
            aria-invalid={!!errors.title}
            onChange={(e) => setV((x) => ({ ...x, title: e.target.value }))}
          />
        </Field>
        <Field label="Team" htmlFor="cr-queue" hint="Offered only on this team's requests">
          <NativeSelect id="cr-queue" value={v.queue} onChange={(e) => setV((x) => ({ ...x, queue: e.target.value as SupportQueue | "" }))}>
            <option value="">Every team</option>
            {(Object.keys(QUEUE_LABELS) as SupportQueue[]).map((q) => (
              <option key={q} value={q}>
                {QUEUE_LABELS[q]}
              </option>
            ))}
          </NativeSelect>
        </Field>
      </div>
      <Field label="Reply text" htmlFor="cr-body" required error={errors.body}>
        <Textarea
          id="cr-body"
          rows={6}
          maxLength={4000}
          value={v.body}
          aria-invalid={!!errors.body}
          onChange={(e) => setV((x) => ({ ...x, body: e.target.value }))}
        />
      </Field>
      <div className="text-xs">
        <p className="text-muted-foreground mb-1">Filled in from the request when used. Tap to insert:</p>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(placeholders).map(([key, label]) => (
            <button
              key={key}
              type="button"
              title={label}
              onClick={() => insert(key)}
              className="border-border hover:border-primary rounded border px-1.5 py-0.5 font-mono text-[11px]"
            >
              {`{{${key}}}`}
              <span className="sr-only">: {label}</span>
            </button>
          ))}
        </div>
      </div>
      {failure && (
        <p className="text-destructive text-xs" role="alert">
          {failure}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" loading={isPending}>
          Save
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function Item({ reply, onEdit }: { reply: CannedReply; onEdit: () => void }) {
  const { remove, isPending } = useCannedReplyAdmin();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const drop = async () => {
    setError(null);
    try {
      await remove(reply.id);
    } catch (err) {
      setError(getErrorMessage(err));
      setConfirming(false);
    }
  };
  return (
    <li className="p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium">{reply.title}</p>
          <p className="text-muted-foreground text-[11px]">
            {reply.queue_label ?? "Every team"} · used {reply.use_count} time{reply.use_count === 1 ? "" : "s"} · edited{" "}
            {timeAgo(reply.updated_at)}
            {reply.updated_by_name ? ` by ${reply.updated_by_name}` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={onEdit}>
            Edit
          </Button>
          {confirming ? (
            <>
              <Button size="sm" variant="destructive" loading={isPending} onClick={() => void drop()}>
                Delete for everyone
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
              Delete
            </Button>
          )}
        </div>
      </div>
      <p className="text-muted-foreground mt-2 line-clamp-3 text-xs whitespace-pre-line">{reply.body}</p>
      {error && (
        <p className="text-destructive mt-1 text-xs" role="alert">
          {error}
        </p>
      )}
    </li>
  );
}

/** /support/replies: the team's saved replies. */
export function CannedReplies() {
  const [page, setPage] = useUrlPage();
  const [query, setQuery] = useState("");
  const q = useDebounced(query.trim(), 300);
  const [queue, setQueue] = useState("");
  const { payload, isLoading, error, refetch } = useCannedReplies({ q: q || undefined, queue: queue || undefined, page });
  const [editing, setEditing] = useState<Draft | null>(null);

  return (
    <AdminPage
      title="Saved replies · የተዘጋጁ መልሶች"
      description="Answers the team gives often. Pick one while replying to a request; the name, request number and team are filled in, and you can still edit the text before sending."
      actions={
        <>
          <Link href="/support" className="text-primary self-center text-xs hover:underline">
            Back to the support desk
          </Link>
          {!editing && (
            <Button size="sm" onClick={() => setEditing(EMPTY)}>
              New saved reply
            </Button>
          )}
        </>
      }
    >
      {editing && (
        <Editor key={editing.id ?? "new"} draft={editing} placeholders={payload?.placeholders ?? {}} onDone={() => setEditing(null)} />
      )}
      <div className="mb-3 flex flex-wrap gap-2">
        <label htmlFor="cr-search" className="sr-only">
          Search saved replies
        </label>
        <Input
          id="cr-search"
          type="search"
          className="h-8 w-full text-xs sm:w-64"
          placeholder="Search title or text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (page) setPage(0);
          }}
        />
        <NativeSelect
          aria-label="Team"
          value={queue}
          onChange={(e) => {
            setQueue(e.target.value);
            if (page) setPage(0);
          }}
        >
          <option value="">All teams</option>
          {(Object.keys(QUEUE_LABELS) as SupportQueue[]).map((k) => (
            <option key={k} value={k}>
              {QUEUE_LABELS[k]}
            </option>
          ))}
        </NativeSelect>
      </div>
      {isLoading ? (
        <LoadingState label="Loading saved replies…" />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !payload?.items.length ? (
        <EmptyState title="No saved replies yet" description="Add the answers your team writes again and again." />
      ) : (
        <ul className="divide-border border-border bg-card divide-y border">
          {payload.items.map((r) => (
            <Item key={r.id} reply={r} onEdit={() => setEditing({ id: r.id, title: r.title, body: r.body, queue: r.queue ?? "" })} />
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={CANNED_PAGE_SIZE} total={payload?.total ?? 0} onPage={setPage} />
    </AdminPage>
  );
}
