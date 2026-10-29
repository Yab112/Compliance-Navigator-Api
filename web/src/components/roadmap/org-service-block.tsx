import Link from "next/link";
import { ReportIssue } from "@/components/feedback/report-issue";
import { formatDate } from "@cn/ui/guday/shared";
import { ConfirmedBadge, formatFee, formatMinutes } from "@cn/ui/organizations/shared";
import { FeeTable } from "@/modules/organizations/pages/service-page";
import { PROXY_LABEL } from "@cn/core/types/organizations";
import type { OrgStepService } from "@/types/roadmap";

/** The issuing organization's own published data for a path step, shown before older catalog data. */
export function OrgServiceBlock({ org }: { org: OrgStepService }) {
  const b = org.branch;
  const serviceUrl = `/organizations/${org.orgSlug}/services/${org.serviceSlug}`;
  return (
    <div className="border-primary/40 bg-card space-y-4 border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-muted-foreground text-[11px] font-semibold uppercase">Published by the organization · ከተቋሙ</p>
          <h4 className="text-sm font-semibold">
            <Link href={serviceUrl} className="hover:underline">
              {org.serviceName}
            </Link>{" "}
            · {org.orgName}
          </h4>
        </div>
        <ConfirmedBadge days={org.confirmedDaysAgo} due={org.confirmationDue} orgName={org.orgName} />
      </div>

      {org.upcomingChange && (
        <p className="rounded border border-sky-200 bg-sky-50 px-3 py-2 text-sky-950">
          <strong>Changes on {formatDate(org.upcomingChange.effective_at)}:</strong> {org.upcomingChange.summary}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <h5 className="font-semibold">Where to go</h5>
          {b ? (
            <>
              <p className="font-medium">
                {b.name}
                {b.window && <span className="bg-secondary text-primary ml-2 rounded px-1.5 py-0.5">{b.window}</span>}
              </p>
              <p className="text-muted-foreground">{[b.address, b.woreda && `Woreda ${b.woreda}`, b.sub_city].filter(Boolean).join(" · ")}</p>
              {b.landmark && <p className="text-muted-foreground">Landmark: {b.landmark}</p>}
              {(b.hours_text || b.hours) && <p>Hours: {b.hours_text || b.hours}</p>}
              {b.hours_note && <p>For this service: {b.hours_note}</p>}
              <p className="flex flex-wrap gap-x-3">
                {(b.service_phone || b.phone) && (
                  <a href={`tel:${(b.service_phone || b.phone)!.replace(/\s/g, "")}`} className="text-primary underline">
                    {b.service_phone || b.phone}
                  </a>
                )}
                {b.map_url && (
                  <a href={b.map_url} target="_blank" rel="noreferrer" className="text-primary underline">
                    Map
                  </a>
                )}
              </p>
              {org.otherBranches > 0 && (
                <Link href={serviceUrl} className="text-primary underline">
                  {org.otherBranches} other branch{org.otherBranches === 1 ? "" : "es"}
                </Link>
              )}
            </>
          ) : (
            <p>{org.delivery === "online" ? "Online only" : "See the service page for branches"}</p>
          )}
          {org.onlineUrl && (
            <a href={org.onlineUrl} target="_blank" rel="noreferrer" className="text-primary block underline">
              Apply online{org.onlineParts ? `: ${org.onlineParts}` : ""}
            </a>
          )}
          {org.appointment.required && (
            <p className="font-medium text-amber-900">
              Book an appointment first{org.appointment.how ? `: ${org.appointment.how}` : ""}
              {org.appointment.phone && ` · ${org.appointment.phone}`}
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <h5 className="font-semibold">Fee and time</h5>
          {org.isFree ? (
            <p className="font-medium">Free</p>
          ) : org.feeSchedule.length > 0 ? (
            <FeeTable rows={org.feeSchedule} currency={org.feeCurrency} />
          ) : (
            <p className="font-medium">{formatFee(org.feeAmountMin, org.feeAmountMax, org.feeCurrency)}</p>
          )}
          {org.feeNotes && <p className="text-muted-foreground">{org.feeNotes}</p>}
          {(org.paymentMethods.length > 0 || org.whereToPay) && (
            <p>Pay: {[org.paymentMethods.join(", "), org.whereToPay].filter(Boolean).join(" · ")}</p>
          )}
          <p>Takes: {org.processingTimeText || formatMinutes(org.processingMinutes)}</p>
          {org.outputValidityMonths && <p>Valid for {org.outputValidityMonths} months</p>}
          {org.proxyAllowed && <p>{PROXY_LABEL[org.proxyAllowed]}</p>}
        </div>
      </div>

      <div>
        <h5 className="mb-1 font-semibold">What to bring</h5>
        {org.noDocumentsRequired ? (
          <p>No documents needed.</p>
        ) : (
          <ul className="space-y-1">
            {org.requirements.map((r) => (
              <li key={r.name} className="flex gap-2">
                <span className="text-primary" aria-hidden>
                  ☐
                </span>
                <span>
                  <span className="font-medium">{r.name}</span>
                  {r.required === "conditional" && <span className="text-muted-foreground"> (only in some cases)</span>}
                  {[
                    r.original_or_copy === "both" ? "original and a copy" : r.original_or_copy,
                    r.copies && `${r.copies} copies`,
                    r.notarized && "notarized",
                    r.translated && "translated",
                    r.max_age_days && `issued in the last ${r.max_age_days} days`,
                  ]
                    .filter(Boolean)
                    .map((t) => ` · ${t}`)
                    .join("")}
                  {r.photo_specs && <span className="text-muted-foreground block">Photo: {r.photo_specs}</span>}
                  {r.issued_by && (
                    <span className="block">
                      From{" "}
                      <Link href={`/organizations/${r.issued_by.org_slug}/services/${r.issued_by.service_slug}`} className="text-primary underline">
                        {r.issued_by.service_name}
                      </Link>{" "}
                      at {r.issued_by.org_name}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
        {org.hasQuestions && (
          <Link href={serviceUrl} className="text-primary mt-1 inline-block underline">
            Answer a few questions to see exactly what applies to you
          </Link>
        )}
      </div>

      {org.steps.length > 0 && (
        <div>
          <h5 className="mb-1 font-semibold">At the office</h5>
          <ol className="list-inside list-decimal space-y-0.5">
            {org.steps.map((s, i) => (
              <li key={i}>
                {s.title}
                {s.location && <span className="text-muted-foreground"> · {s.location}</span>}
                {s.estimated_minutes != null && <span className="text-muted-foreground"> · about {s.estimated_minutes} min</span>}
              </li>
            ))}
          </ol>
        </div>
      )}

      {org.rejectionReasons.length > 0 && (
        <div>
          <h5 className="mb-1 font-semibold">Why people get sent back</h5>
          <ul className="text-muted-foreground list-inside list-disc">
            {org.rejectionReasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-muted-foreground border-t pt-2">
        {[
          org.legalBasis && `${org.legalBasis}${org.legalReferenceNumber ? ` No. ${org.legalReferenceNumber}` : ""}`,
          org.contact.phone && `Questions: ${org.contact.name ? `${org.contact.name}, ` : ""}${org.contact.phone}`,
          org.languages.length > 0 && `Languages: ${org.languages.join(", ")}`,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <ReportIssue targetType="org_service" targetId={org.serviceId} label="Tell the organization something is wrong" />
    </div>
  );
}
