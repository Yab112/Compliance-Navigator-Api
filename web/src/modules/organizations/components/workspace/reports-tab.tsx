"use client";

import { useState } from "react";
import { useOrgAction, useOrgReports } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Textarea } from "@cn/ui/textarea";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { LoadingState, formatDate } from "@cn/ui/guday/shared";
import type { OrgReport } from "@cn/core/types/organizations";
import { Panel } from "@cn/ui/organizations/shared";

export function ReportsTab({ orgId }: { orgId: string }) {
  const { data, isLoading } = useOrgReports(orgId);
  const reports = data?.payload.reports ?? [];
  if (isLoading) return <LoadingState />;
  return (
    <Panel title="Reports from the public" am="ከሕዝብ የመጡ ሪፖርቶች">
      <p className="text-muted-foreground mb-4 text-sm">
        People who found something wrong on your service pages. Fix the service if needed, then reply. Your reply goes to the platform
        team, who check it and close the report.
      </p>
      {reports.length === 0 ? (
        <p className="text-muted-foreground text-sm">No reports right now.</p>
      ) : (
        <ul className="divide-border divide-y">
          {reports.map((r) => (
            <ReportItem key={r.id} orgId={orgId} report={r} />
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ReportItem({ orgId, report }: { orgId: string; report: OrgReport }) {
  const action = useOrgAction();
  const [reply, setReply] = useState(report.org_response ?? "");
  const [err, setErr] = useState<string | null>(null);
  const respond = async (verdict: "fixed" | "correct") => {
    setErr(null);
    try {
      await action.mutateAsync({ url: apiPaths.org.report(orgId, report.id), method: MTD.POST, body: { verdict, response: reply.trim() } });
    } catch (e) {
      setErr(getErrorMessage(e));
    }
  };
  return (
    <li className="space-y-2 py-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={cn("rounded px-2 py-0.5 font-medium", report.status === "open" ? "bg-amber-100 text-amber-900" : "bg-muted")}>
          {report.status === "open" ? (report.org_response ? "answered, waiting for staff" : "open") : report.status === "resolved" ? "closed, fixed" : "closed"}
        </span>
        <span className="font-medium">{report.service_name ?? "Service"}</span>
        <span className="text-muted-foreground">{formatDate(report.created_at)}</span>
      </div>
      <p className="text-sm">“{report.message}”</p>
      {report.status === "open" ? (
        <div className="space-y-2">
          {report.org_response && (
            <p className="text-muted-foreground text-sm">
              You said {report.org_verdict === "fixed" ? "it is fixed" : "the information is correct"}: {report.org_response}. You can change your reply
              until staff close the report.
            </p>
          )}
          <Textarea rows={2} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="What you checked or changed" aria-label="Reply" />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={reply.trim().length < 2} loading={action.isPending} onClick={() => void respond("fixed")}>
              We fixed it
            </Button>
            <Button size="sm" variant="outline" disabled={reply.trim().length < 2 || action.isPending} onClick={() => void respond("correct")}>
              Information is correct
            </Button>
          </div>
        </div>
      ) : (
        <>
          {report.org_response && <p className="text-muted-foreground text-sm">Your reply: {report.org_response}</p>}
          {report.resolution_note && <p className="text-muted-foreground text-sm">Platform team: {report.resolution_note}</p>}
        </>
      )}
      {err && <p className="text-destructive text-xs">{err}</p>}
    </li>
  );
}
