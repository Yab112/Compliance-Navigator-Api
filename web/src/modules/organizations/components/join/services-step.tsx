"use client";

import { useState } from "react";
import { useImportServices, useWorkingService } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { env } from "@cn/core/config/env";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";
import type { ImportReport, MemberOrganization, OrgServiceListItem } from "@cn/core/types/organizations";
import { ServiceForm } from "@/modules/organizations/components/service-form";
import { CompletenessMeter, Panel, ServiceStatusChip } from "@cn/ui/organizations/shared";
import { StepActions } from "@/modules/organizations/components/join/step-actions";

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
      <ImportPanel orgId={org.id} />
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

function ImportPanel({ orgId }: { orgId: string }) {
  const importer = useImportServices(orgId);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = async (dryRun: boolean) => {
    if (!file) return;
    setError(null);
    try {
      setReport(await importer.mutateAsync({ file, dryRun }));
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  const templateUrl = `${env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")}/${apiPaths.organizations.importTemplate}`;

  return (
    <Panel title="Add many services from a spreadsheet" am="ከተመን ሉህ ማስገባት">
      <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm">
        <li>
          <a href={templateUrl} className="text-primary font-medium underline">
            Download the template
          </a>{" "}
          and open it in Excel, LibreOffice or Google Sheets. Row 2 explains each column; row 3 is an example.
        </li>
        <li>Fill one row per service. Put several documents or steps in one cell separated by semicolons.</li>
        <li>Save as CSV (UTF-8), upload it, check the report, then add the services as drafts.</li>
      </ol>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input type="file" accept=".csv,text/csv" aria-label="Services CSV file" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setReport(null); }} />
        <Button variant="outline" disabled={!file} loading={importer.isPending && !report} onClick={() => void run(true)}>
          Check the file
        </Button>
      </div>
      {error && <p className="text-destructive mt-2 text-sm">{error}</p>}
      {report && (
        <div className="mt-4 space-y-3">
          <p className="text-sm">
            {report.dry_run ? (
              <>
                <strong>{report.ready}</strong> ready to add, <strong>{report.errors}</strong> with problems.
              </>
            ) : (
              <>
                <strong>{report.created}</strong> services added as drafts. Open each one to finish the details, then submit.
              </>
            )}
          </p>
          <ul className="divide-border max-h-80 divide-y overflow-y-auto rounded-md border text-sm">
            {report.rows.map((r) => (
              <li key={r.row} className="px-3 py-2">
                <p className={r.status === "error" ? "text-destructive font-medium" : "font-medium"}>
                  Row {r.row}: {r.name || "(no name)"} · {r.status === "ready" ? "ready" : r.status === "created" ? "added" : "not added"}
                </p>
                {r.errors.map((e) => (
                  <p key={e} className="text-destructive text-xs">✕ {e}</p>
                ))}
                {r.warnings.map((w) => (
                  <p key={w} className="text-xs text-amber-800">▲ {w}</p>
                ))}
              </li>
            ))}
          </ul>
          {report.dry_run && report.ready > 0 && (
            <Button loading={importer.isPending} onClick={() => void run(false)}>
              Add {report.ready} service{report.ready === 1 ? "" : "s"} as drafts
            </Button>
          )}
        </div>
      )}
    </Panel>
  );
}
