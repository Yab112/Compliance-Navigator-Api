"use client";

import Link from "next/link";
import { useState } from "react";
import { useOrgAction } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { EmptyState, formatDate } from "@cn/ui/guday/shared";
import type { MemberOrganization, OrgServiceListItem } from "@cn/core/types/organizations";
import { CompletenessMeter, ServiceStatusChip } from "@cn/ui/organizations/shared";
import { ServiceImportPanel } from "@/modules/organizations/components/service-import";

export function ServicesTab({ org, services }: { org: MemberOrganization; services: OrgServiceListItem[] }) {
  const action = useOrgAction();
  const [msg, setMsg] = useState<string | null>(null);
  // A suspended organization can't import or vouch for its services until staff lift the suspension
  const active = org.status !== "suspended";
  if (!services.length) {
    return (
      <div className="space-y-4">
        <EmptyState title="No services yet">
          <p className="mb-4">
            Describe each service people come to you for: documents to bring, fees, branches and windows, the questions that
            change the list, and the steps at the office. Add them one by one, or many at once from a spreadsheet below.
          </p>
          <Link href={`/org/${org.id}/services/new`}>
            <Button>Add your first service</Button>
          </Link>
        </EmptyState>
        {active && <ServiceImportPanel orgId={org.id} />}
      </div>
    );
  }
  const due = services.filter((s) => s.confirmation_due);
  const confirm = async (url: string) => {
    setMsg(null);
    try {
      const res = await action.mutateAsync({ url, method: MTD.POST });
      setMsg(`Confirmed ${(res as { confirmed?: number }).confirmed ?? 1} service(s). Thank you.`);
    } catch (e) {
      setMsg(getErrorMessage(e));
    }
  };
  return (
    <div className="space-y-4">
      {active && due.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span>
            {due.length} live service{due.length === 1 ? " is" : "s are"} due for the 90-day check. If nothing changed, confirm
            they are still accurate. If something changed, edit the service.
          </span>
          <Button size="sm" loading={action.isPending} onClick={() => void confirm(apiPaths.org.confirmAll(org.id))}>
            Confirm all are still accurate
          </Button>
        </div>
      )}
      {msg && <p className="text-primary text-sm">{msg}</p>}
      <ul className="border-border bg-card divide-border divide-y rounded-md border">
        {services.map((s) => (
          <li key={s.id} className="flex flex-wrap items-start justify-between gap-3 p-4">
            <div className="min-w-0 flex-1">
              <Link href={`/org/${org.id}/services/${s.id}`} className="text-gov-ink font-semibold hover:underline">
                {s.name}
              </Link>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <ServiceStatusChip status={s.status} isLive={s.is_live} />
                <span className="text-muted-foreground text-xs">
                  {s.version ? `Version ${s.version} · ` : ""}updated {formatDate(s.updated_at)}
                </span>
                {s.is_live && (
                  <span className={cn("text-xs", s.confirmation_due ? "font-semibold text-amber-800" : "text-muted-foreground")}>
                    {s.confirmed_days_ago == null ? "Never confirmed" : `Confirmed ${s.confirmed_days_ago} days ago`}
                  </span>
                )}
              </div>
              {s.scheduled_change && (
                <p className="mt-1 text-sm text-sky-900">
                  Approved change from {formatDate(s.scheduled_change.effective_at)}: {s.scheduled_change.summary}
                </p>
              )}
              {s.status === "changes_requested" && s.admin_note && <p className="mt-1 text-sm text-amber-800">The platform team asked: {s.admin_note}</p>}
              {s.completeness && <CompletenessMeter completeness={s.completeness} compact className="mt-2 max-w-md" />}
            </div>
            <div className="flex gap-2">
              {active && s.is_live && (
                <Button variant="outline" size="sm" onClick={() => void confirm(apiPaths.org.confirm(org.id, s.id))}>
                  Still accurate
                </Button>
              )}
              <Link href={`/org/${org.id}/services/${s.id}`}>
                <Button variant="outline" size="sm">
                  Edit
                </Button>
              </Link>
            </div>
          </li>
        ))}
      </ul>
      {active && <ServiceImportPanel orgId={org.id} />}
    </div>
  );
}
