"use client";

import { useState } from "react";
import { useWorkingService } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";
import type { MemberOrganization, OrgServiceListItem } from "@cn/core/types/organizations";
import { ServiceForm } from "@/modules/organizations/components/service-form";
import { CompletenessMeter, Panel, ServiceStatusChip } from "@cn/ui/organizations/shared";
import { StepActions } from "@/modules/organizations/components/join/step-actions";
import { ServiceImportPanel } from "@/modules/organizations/components/service-import";

const PATH_FIELDS: [string, string][] = [
  ["Documents to bring", "Each document, original or copy, how many, notarized or translated, how recent. This is the checklist people carry."],
  ["Fees and payment", "Every price line (citizens, foreigners, companies, urgent), how and where to pay. People arrive with the exact amount."],
  ["Branch, window and hours", "Which branch, which window, the weekly hours and lunch break. Nobody arrives at a closed office."],
  ["Processing time", "Added up across all the offices on a path, so people can plan their days."],
  ["Questions that change the list", "Renting or owning, citizen or foreigner. Each person sees only what applies to them."],
  ["Appointments and applying for someone", "Whether to book first, and whether an agent may apply with a power of attorney."],
  ["What people receive", "The document you issue and how long it's valid. Other organizations that require it link to you."],
  ["Legal basis and contact", "The proclamation or directive, and who answers questions."],
];

export function ServicesStep({ org, services, onBack, onNext }: { org: MemberOrganization; services: OrgServiceListItem[]; onBack: () => void; onNext: () => void }) {
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const live = services.filter((s) => s.status !== "archived");

  if (editing) {
    return <EmbeddedEditor org={org} serviceId={editing === "new" ? null : editing} services={services} onDone={() => setEditing(null)} />;
  }
  return (
    <div className="space-y-6">
      <Panel title="4. Your services" am="አገልግሎቶችዎ">
        <details className="bg-secondary/40 mb-5 rounded-md p-4" open={live.length === 0}>
          <summary className="cursor-pointer text-sm font-semibold">What we show on a path, and why each part matters</summary>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            {PATH_FIELDS.map(([t, d]) => (
              <div key={t}>
                <dt className="text-sm font-medium">{t}</dt>
                <dd className="text-muted-foreground text-sm">{d}</dd>
              </div>
            ))}
          </dl>
        </details>
        {live.length === 0 ? (
          <p className="text-muted-foreground mb-4 text-sm">No services yet. Add them one by one, or many at once from a spreadsheet below.</p>
        ) : (
          <ul className="divide-border mb-4 divide-y">
            {live.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{s.name}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <ServiceStatusChip status={s.status} isLive={s.is_live} />
                  </div>
                  {s.completeness && <CompletenessMeter completeness={s.completeness} compact className="mt-2 max-w-md" />}
                </div>
                <Button variant="outline" onClick={() => setEditing(s.id)}>
                  Edit
                </Button>
              </li>
            ))}
          </ul>
        )}
        <Button onClick={() => setEditing("new")}>+ Add a service</Button>
      </Panel>
      <ServiceImportPanel orgId={org.id} />
      <StepActions onBack={onBack} next={onNext} nextLabel="Continue" />
    </div>
  );
}

function EmbeddedEditor({ org, serviceId, services, onDone }: { org: MemberOrganization; serviceId: string | null; services: OrgServiceListItem[]; onDone: () => void }) {
  // Only an existing service is loaded; a new one keeps its form mounted after the first save
  const working = useWorkingService(org.id, serviceId);
  const loaded = working.data?.payload.service;
  if (serviceId && !loaded) return working.isError ? <ErrorState message={working.error?.message ?? "Could not load"} /> : <LoadingState />;
  return (
    <ServiceForm
      orgId={org.id}
      org={org}
      serviceId={serviceId}
      loaded={loaded}
      services={services}
      onExit={onDone}
      exitLabel="Back to services list"
    />
  );
}
