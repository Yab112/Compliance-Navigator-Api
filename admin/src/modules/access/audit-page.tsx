"use client";

import { useEffect, useState } from "react";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { AdminPage } from "@/modules/components/admin-page";
import { NativeSelect } from "@/modules/shared/native-select";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { PAGE_SIZE, useAudit, type AuditFilters } from "./api";
import { AuditTable, Gate } from "./shared";

const ACTION_GROUPS = [
  { value: "", label: "Everything" },
  { value: "auth.", label: "Sign-ins and passwords" },
  { value: "approval.", label: "Approvals" },
  { value: "staff.", label: "Staff changes" },
  { value: "role.", label: "Role changes" },
  { value: "access.denied", label: "Refused actions" },
  { value: "payouts.", label: "Payouts" },
  { value: "settings.", label: "Settings" },
  { value: "providers.", label: "Providers" },
  { value: "users.", label: "Public users" },
];

function AuditList() {
  const [draft, setDraft] = useState<AuditFilters>({});
  const [filters, setFilters] = useState<AuditFilters>({});
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(PAGE_SIZE);

  // Text boxes apply after a short pause; a new filter starts from the first page
  useEffect(() => {
    const t = setTimeout(() => {
      if (JSON.stringify(draft) !== JSON.stringify(filters)) {
        setFilters(draft);
        setPage(0);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [draft, filters, setPage]);

  const { payload, isLoading, error, refetch } = useAudit(filters, page, size);
  const set = (k: keyof AuditFilters) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setDraft((d) => ({ ...d, [k]: e.target.value }));

  return (
    <AdminPage
      title="Audit log · የክትትል መዝገብ"
      description="Everything staff did in this workspace: sign-ins, every change with its result, refused actions and approvals. Entries can't be edited or deleted here."
    >
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="flex flex-col gap-1">
          <Label htmlFor="audit-actor">Who (email)</Label>
          <Input id="audit-actor" value={draft.actor ?? ""} onChange={set("actor")} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="audit-action">What</Label>
          <NativeSelect id="audit-action" value={draft.action ?? ""} onChange={set("action")}>
            {ACTION_GROUPS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="audit-target">Target contains</Label>
          <Input id="audit-target" value={draft.target ?? ""} onChange={set("target")} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="audit-since">From</Label>
          <Input id="audit-since" type="date" value={draft.since ?? ""} onChange={set("since")} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="audit-until">To</Label>
          <Input id="audit-until" type="date" value={draft.until ?? ""} onChange={set("until")} />
        </div>
      </div>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !payload?.items.length ? (
        <EmptyState title="Nothing matches" />
      ) : (
        <AuditTable items={payload.items} />
      )}
      <Pager page={page} pageSize={size} total={payload?.total ?? 0} onPage={setPage} onPageSize={setSize} />
    </AdminPage>
  );
}

export function AuditPage() {
  return (
    <Gate perm="audit.view">
      <AuditList />
    </Gate>
  );
}
