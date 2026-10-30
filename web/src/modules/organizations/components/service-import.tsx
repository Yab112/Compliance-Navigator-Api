"use client";

import { useState } from "react";
import { useImportServices } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { env } from "@cn/core/config/env";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import type { ImportReport } from "@cn/core/types/organizations";
import { Panel } from "@cn/ui/organizations/shared";

/** File types the import accepts. The API picks its reader by file extension, so adding a format
 *  (PDF, DOCX, JSON are planned) is a new entry here plus a parser in api/services/org_import. */
const IMPORT_FORMATS = [{ label: "CSV", accept: [".csv", "text/csv"] }];

const formatNames = IMPORT_FORMATS.map((f) => f.label).join(", ");
const acceptAttr = IMPORT_FORMATS.flatMap((f) => f.accept).join(",");

/** Check a file of services, see each row's result, then add the valid rows as drafts. Used in the
 *  registration wizard and the workspace Services tab. Drafts go through the normal submit and review. */
export function ServiceImportPanel({ orgId }: { orgId: string }) {
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
        <Input
          type="file"
          accept={acceptAttr}
          aria-label={`Services file (${formatNames})`}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setReport(null);
            setError(null);
          }}
        />
        <Button variant="outline" disabled={!file} loading={importer.isPending && !report} onClick={() => void run(true)}>
          Check the file
        </Button>
      </div>
      <p className="text-muted-foreground mt-1 text-xs">Accepted: {formatNames}. Nothing is added until you confirm.</p>
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
                <strong>{report.created}</strong> {report.created === 1 ? "service" : "services"} added as drafts. Open each one to finish the details, then submit it for review.
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
