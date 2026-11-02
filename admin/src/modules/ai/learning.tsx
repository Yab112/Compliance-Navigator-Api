"use client";

import { useState } from "react";
import { useAdminMutation, useAdminQuery } from "@cn/core/api/admin/use-admin-query";
import { Button } from "@cn/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@cn/ui/card";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { formatDateTime } from "@cn/core/lib/format";
import { NativeSelect } from "@/modules/shared/native-select";
import { STAT_STRIP, StatTile } from "@/modules/shared/stat-tile";
import { ErrorState, LoadingState } from "@/modules/shared/states";

const p = apiPaths.admin;

type FindingStatus = "new" | "approved" | "rejected" | "done";
type Finding = {
  id: number;
  kind: string;
  summary: string;
  next_action: string;
  action_type: string;
  examples: string[];
  seen_count: number;
  last_seen: string;
  status: FindingStatus;
  reviewed_by: string | null;
  note: string | null;
};
type Run = {
  id: number;
  triggered_by: string;
  started_at: string;
  finished_at: string | null;
  findings_new: number;
  findings_updated: number;
  summary: { turns_read?: number; by_kind?: Record<string, number> };
};
type GuardRow = {
  id: number;
  conversation_id: string | null;
  tool: string;
  args: Record<string, unknown>;
  decision: "allowed" | "denied" | "error";
  reason: string | null;
  duration_ms: number;
  created_at: string;
};

const KIND_LABEL: Record<string, string> = {
  missing_service: "Missing service",
  user_correction: "Someone said it was wrong",
  grounding_failed: "AI stated an unsourced number",
  low_confidence: "Unsure messages",
  denied_request: "Guard refused",
  tool_error: "Tool broke",
};

function FindingRow({ f }: { f: Finding }) {
  const { run, isPending } = useAdminMutation<Finding, { status: FindingStatus; note?: string }>([["assistant", "findings"]]);
  const [note, setNote] = useState(f.note ?? "");
  const [error, setError] = useState<string | null>(null);
  const decide = async (status: FindingStatus) => {
    setError(null);
    try {
      await run(p.assistantFinding(f.id), MTD.PATCH, { status, note: note || undefined });
    } catch (e) {
      setError(getErrorMessage(e, "Couldn't save the decision"));
    }
  };
  return (
    <li className="border-border rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="bg-muted rounded px-1.5 py-0.5 font-medium">{KIND_LABEL[f.kind] ?? f.kind}</span>
        <span className="text-muted-foreground">
          seen {f.seen_count}× · last {formatDateTime(f.last_seen)} · {f.status}
          {f.reviewed_by ? ` by ${f.reviewed_by}` : ""}
        </span>
      </div>
      <p className="mt-1.5 text-sm">{f.summary}</p>
      <p className="mt-1 text-sm">
        <span className="font-medium">Next action: </span>
        {f.next_action}
      </p>
      {f.examples.length > 0 && (
        <ul className="text-muted-foreground mt-1.5 list-disc space-y-0.5 pl-5 text-xs">
          {f.examples.slice(0, 3).map((e, i) => (
            <li key={i} className="break-words">
              {typeof e === "string" ? e : JSON.stringify(e)}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (source, who checked it)"
          aria-label="Note"
          maxLength={1000}
          className="border-input bg-background h-8 min-w-0 flex-1 rounded-md border px-2 text-xs"
        />
        <Button size="sm" disabled={isPending} onClick={() => decide("approved")}>
          Approve
        </Button>
        <Button size="sm" variant="secondary" disabled={isPending} onClick={() => decide("done")}>
          Done
        </Button>
        <Button size="sm" variant="ghost" disabled={isPending} onClick={() => decide("rejected")}>
          Reject
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-destructive mt-1 text-[11px]">
          {error}
        </p>
      )}
    </li>
  );
}

/** What the assistant found going wrong, and what it proposes; staff decide every one. */
export function LearningSection() {
  const [status, setStatus] = useState<FindingStatus | "">("new");
  const findings = useAdminQuery<{ items: Finding[]; totals: Partial<Record<FindingStatus, number>> }>(
    ["assistant", "findings", status],
    `${p.assistantFindings}${status ? `?status=${status}` : ""}`,
  );
  const runs = useAdminQuery<{ items: Run[] }>(["assistant", "findings", "runs"], `${p.assistantLearnRuns}?limit=5`);
  const learn = useAdminMutation<Run & { new: number; updated: number; turns_read: number }, undefined>([["assistant", "findings"]]);
  const [message, setMessage] = useState<string | null>(null);
  const last = runs.payload?.items?.[0];
  const totals = findings.payload?.totals ?? {};

  return (
    <Card>
      <CardHeader>
        <CardTitle>Learning · what the assistant found and what it proposes</CardTitle>
        <CardDescription>
          A learning run reads the conversations since the last run and the guard log, groups what went wrong (services
          we don&rsquo;t have, people saying an answer was wrong, replies with unsourced numbers) and proposes a next
          action for each. Nothing changes the data or the model by itself: you approve, reject or mark each one done.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            disabled={learn.isPending}
            onClick={async () => {
              setMessage(null);
              try {
                const d = await learn.run(p.assistantLearn, MTD.POST);
                setMessage(`Read ${d?.turns_read ?? 0} messages: ${d?.new ?? 0} new finding(s), ${d?.updated ?? 0} seen again.`);
              } catch (e) {
                setMessage(getErrorMessage(e, "The learning run failed"));
              }
            }}
          >
            {learn.isPending ? "Learning…" : "Run learning now"}
          </Button>
          <span className="text-muted-foreground text-xs">
            {last ? `Last run ${formatDateTime(last.started_at)} by ${last.triggered_by}` : "Not run yet"}
          </span>
          {message && <span className="text-xs">{message}</span>}
        </div>
        <div className={`${STAT_STRIP} mt-4`}>
          <StatTile label="New" value={totals.new ?? 0} />
          <StatTile label="Approved, to do" value={totals.approved ?? 0} />
          <StatTile label="Done" value={totals.done ?? 0} />
          <StatTile label="Rejected" value={totals.rejected ?? 0} />
        </div>
        <div className="mt-4 flex items-center gap-2">
          <NativeSelect value={status} onChange={(e) => setStatus(e.target.value as FindingStatus | "")} aria-label="Show">
            <option value="new">New</option>
            <option value="approved">Approved, to do</option>
            <option value="done">Done</option>
            <option value="rejected">Rejected</option>
            <option value="">All</option>
          </NativeSelect>
        </div>
        {findings.isLoading ? (
          <LoadingState />
        ) : findings.error ? (
          <ErrorState message="Couldn't load the findings" error={findings.error} onRetry={() => findings.refetch()} />
        ) : !findings.payload?.items.length ? (
          <p className="text-muted-foreground mt-3 text-sm">Nothing here. Run learning to look at recent conversations.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {findings.payload.items.map((f) => (
              <FindingRow key={`${f.id}:${f.status}`} f={f} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/** Every request the AI made for data or an action, and what the guard decided. */
export function GuardSection() {
  const [decision, setDecision] = useState<"" | "allowed" | "denied" | "error">("");
  const log = useAdminQuery<{ items: GuardRow[]; last7Days: { tool: string; decision: string; n: number }[] }>(
    ["assistant", "guard", decision],
    `${p.assistantGuard}?limit=50${decision ? `&decision=${decision}` : ""}`,
  );
  const sums = (log.payload?.last7Days ?? []).reduce<Record<string, number>>((acc, r) => {
    acc[r.decision] = (acc[r.decision] ?? 0) + r.n;
    return acc;
  }, {});
  return (
    <Card>
      <CardHeader>
        <CardTitle>Guard · the AI&rsquo;s requests for data</CardTitle>
        <CardDescription>
          The AI never reads the database. It asks the guard for one of a fixed list of tools; the guard checks the request
          (allowed tool, exact fields, limits per message), runs our own code, removes personal data from the answer and
          records the decision here.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className={STAT_STRIP}>
          <StatTile label="Allowed, 7 days" value={sums.allowed ?? 0} />
          <StatTile label="Refused, 7 days" value={sums.denied ?? 0} tone={sums.denied ? "attention" : "default"} />
          <StatTile label="Errors, 7 days" value={sums.error ?? 0} tone={sums.error ? "attention" : "default"} />
        </div>
        <div className="mt-4">
          <NativeSelect value={decision} onChange={(e) => setDecision(e.target.value as typeof decision)} aria-label="Decision">
            <option value="">All requests</option>
            <option value="denied">Refused</option>
            <option value="error">Errors</option>
            <option value="allowed">Allowed</option>
          </NativeSelect>
        </div>
        {log.isLoading ? (
          <LoadingState />
        ) : log.error ? (
          <ErrorState message="Couldn't load the guard log" error={log.error} onRetry={() => log.refetch()} />
        ) : !log.payload?.items.length ? (
          <p className="text-muted-foreground mt-3 text-sm">No requests yet. They appear once the AI assistant is switched on.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="py-1.5 pr-3 font-medium">When</th>
                  <th className="py-1.5 pr-3 font-medium">Tool</th>
                  <th className="py-1.5 pr-3 font-medium">Asked for</th>
                  <th className="py-1.5 pr-3 font-medium">Decision</th>
                </tr>
              </thead>
              <tbody>
                {log.payload.items.map((r) => (
                  <tr key={r.id} className="border-border border-t align-top">
                    <td className="py-1.5 pr-3 whitespace-nowrap">{formatDateTime(r.created_at)}</td>
                    <td className="py-1.5 pr-3">{r.tool}</td>
                    <td className="py-1.5 pr-3 break-all">{JSON.stringify(r.args)}</td>
                    <td className="py-1.5 pr-3">
                      {r.decision}
                      {r.reason ? <span className="text-muted-foreground"> · {r.reason}</span> : null} · {r.duration_ms} ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
