"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { Button } from "@cn/ui/button";
import { Label } from "@cn/ui/label";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { Textarea } from "@cn/ui/textarea";
import { AdminPage } from "@/modules/components/admin-page";
import { NativeSelect } from "@/modules/shared/native-select";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import {
  PAGE_SIZE,
  useApprovalCount,
  useApprovals,
  useCan,
  useDecide,
  type Approval,
  type ApprovalBox,
} from "./api";
import { ApprovalChange, ApprovalStatusBadge, Notice, When } from "./shared";

function ApprovalCard({ approval, box }: { approval: Approval; box: ApprovalBox }) {
  const { me } = useCan();
  const { decide, isPending } = useDecide();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const mine = approval.requested_by === me?.user.id;
  const canDecide = box === "waiting" && approval.status === "pending" && !mine;
  const noteId = `note-${approval.id}`;

  const act = async (how: "approve" | "reject" | "cancel") => {
    setError(null);
    setMessage(null);
    if (how === "reject" && !note.trim()) return setError("Write why you are rejecting it.");
    try {
      const res = await decide(approval.id, how, note.trim() || undefined);
      const status = res.approval.status;
      setMessage(
        status === "executed"
          ? "Approved. The change has been made."
          : status === "failed"
            ? `Approved, but the change could not be made: ${res.approval.error ?? "unknown error"}`
            : `Request ${status}.`,
      );
    } catch (e) {
      setError(getErrorMessage(e, "Could not record the decision"));
    }
  };

  return (
    <li className="border-border bg-card border p-4 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">{approval.title}</p>
        <ApprovalStatusBadge status={approval.status} />
      </div>
      <p className="text-muted-foreground mt-1">
        Asked by {approval.requested_by_email} <When at={approval.created_at} />
        {approval.status === "pending" && (
          <>
            {" "}
            · expires <When at={approval.expires_at} />
          </>
        )}
        {" "}· approver needs <span className="font-mono">{approval.approver_permission}</span>
      </p>
      <div className="mt-3">
        <ApprovalChange approval={approval} />
      </div>
      {approval.decided_by_email && (
        <p className="text-muted-foreground mt-2">
          Decided by {approval.decided_by_email} <When at={approval.decided_at} />
          {approval.decision_note && <>: &ldquo;{approval.decision_note}&rdquo;</>}
        </p>
      )}
      {approval.error && <p className="text-destructive mt-2">Could not be carried out: {approval.error}</p>}
      {canDecide && (
        <div className="mt-3 flex flex-col gap-2">
          <Label htmlFor={noteId}>Note (needed to reject)</Label>
          <Textarea id={noteId} value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} className="max-w-lg" />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={isPending} onClick={() => act("approve")}>
              Approve and carry out
            </Button>
            <Button size="sm" variant="outline" disabled={isPending} onClick={() => act("reject")}>
              Reject
            </Button>
          </div>
        </div>
      )}
      {mine && approval.status === "pending" && (
        <Button size="sm" variant="outline" className="mt-3" disabled={isPending} onClick={() => act("cancel")}>
          Cancel my request
        </Button>
      )}
      <div className="mt-2">
        <Notice message={error} tone="error" />
        <Notice message={message} />
      </div>
    </li>
  );
}

const TABS: { id: ApprovalBox; label: string }[] = [
  { id: "waiting", label: "Waiting for me" },
  { id: "mine", label: "My requests" },
  { id: "all", label: "History" },
];

export function ApprovalsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const box = (TABS.find((t) => t.id === params.get("box"))?.id ?? "waiting") as ApprovalBox;
  const [status, setStatus] = useState("");
  const [page, setPage] = useUrlPage();
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const counts: Record<ApprovalBox, number | undefined> = {
    waiting: useApprovalCount("waiting"),
    mine: useApprovalCount("mine"),
    all: undefined,
  };
  const { payload, isLoading, error, refetch } = useApprovals(box, page, box === "waiting" ? "" : status);

  const select = (next: ApprovalBox, focus = false) => {
    const sp = new URLSearchParams(params.toString());
    sp.set("box", next);
    sp.delete("page");
    setStatus("");
    router.replace(`${pathname}?${sp}`, { scroll: false });
    if (focus) tabRefs.current[next]?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    const i = TABS.findIndex((t) => t.id === box);
    const moves: Record<string, number> = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: TABS.length - 1 };
    if (!(e.key in moves)) return;
    e.preventDefault();
    select(TABS[(moves[e.key] + TABS.length) % TABS.length].id, true);
  };

  return (
    <AdminPage
      title="Approvals · ማጽደቂያዎች"
      description="Risky changes (money and tax settings, large payouts, staff and roles, deleting data sources) wait here until a second staff member approves them. Nobody approves their own request."
    >
      <div role="tablist" aria-label="Approval lists" className="border-border mb-4 flex gap-1 overflow-x-auto border-b" onKeyDown={onKeyDown}>
        {TABS.map((t) => (
          <button
            key={t.id}
            ref={(el) => {
              tabRefs.current[t.id] = el;
            }}
            id={`approvals-tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={box === t.id}
            aria-controls="approvals-panel"
            tabIndex={box === t.id ? 0 : -1}
            onClick={() => select(t.id)}
            className={cn(
              "-mb-px shrink-0 border-b-2 border-transparent px-3 py-2 text-xs",
              box === t.id ? "border-primary font-medium" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
            {counts[t.id] != null && <span className="text-muted-foreground tabular-nums"> ({counts[t.id]})</span>}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="approvals-panel" aria-labelledby={`approvals-tab-${box}`}>
        {box !== "waiting" && (
          <NativeSelect className="mb-4" value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }} aria-label="Filter by status">
            <option value="">Any status</option>
            {["pending", "executed", "rejected", "failed", "cancelled", "expired"].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </NativeSelect>
        )}
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
        ) : !payload?.items.length ? (
          <EmptyState title={box === "waiting" ? "Nothing is waiting for you" : "No requests"} />
        ) : (
          <ul className="space-y-3">
            {payload.items.map((a) => (
              <ApprovalCard key={`${a.id}-${a.status}`} approval={a} box={box} />
            ))}
          </ul>
        )}
        <Pager page={page} pageSize={PAGE_SIZE} total={payload?.total ?? 0} onPage={setPage} />
      </div>
    </AdminPage>
  );
}
