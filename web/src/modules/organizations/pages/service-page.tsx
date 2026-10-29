"use client";

import Link from "next/link";
import { usePublicService, useServicePath } from "@/api/organizations";
import { ReportIssue } from "@/components/feedback/report-issue";
import { PageShell } from "@/components/layout/page-shell";
import { apiAssetUrl } from "@/lib/api";
import { ErrorState, LoadingState, formatDate } from "@/modules/guday/components/shared";
import { AUDIENCE_LABEL, FEE_CATEGORY_LABEL, PROXY_LABEL, type FeeRow, type PublicService } from "@/types/organizations";
import { EligibilityCheck, RequirementItem } from "../components/eligibility-check";
import { PathFlow } from "../components/path-flow";
import { ConfirmedBadge, Panel, VerifiedBadge, formatFee, formatMinutes } from "../components/shared";

const DELIVERY = { in_person: "In person", online: "Online", both: "Online or in person" } as const;

function feeLabel(r: FeeRow) {
  return [FEE_CATEGORY_LABEL[r.category], r.speed === "urgent" ? "urgent" : null].filter(Boolean).join(", ");
}

/** Price lines: who pays what, for which speed. */
export function FeeTable({ rows, currency }: { rows: FeeRow[]; currency?: string }) {
  return (
    <table className="w-full text-sm">
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="border-border border-b last:border-0 align-top">
            <td className="py-1.5 pr-2">
              {feeLabel(r)}
              {r.covers && <span className="text-muted-foreground block text-xs">{r.covers}</span>}
              {r.notes && <span className="text-muted-foreground block text-xs">{r.notes}</span>}
            </td>
            <td className="py-1.5 text-right font-semibold whitespace-nowrap">{formatFee(r.amount_min, r.amount_max, r.currency ?? currency)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function UpcomingChange({ change }: { change: NonNullable<PublicService["upcoming_change"]> }) {
  return (
    <div className="mb-6 rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950">
      <p className="font-semibold">Upcoming change from {formatDate(change.effective_at)} · ከ{formatDate(change.effective_at)} ጀምሮ ለውጥ</p>
      {change.summary && <p className="mt-1">{change.summary}</p>}
      {change.fee_schedule && change.fee_schedule.length > 0 && (
        <div className="mt-2 max-w-sm">
          <FeeTable rows={change.fee_schedule} />
        </div>
      )}
    </div>
  );
}

export function ServicePage({ slug, serviceSlug }: { slug: string; serviceSlug: string }) {
  const { data, isLoading, isError, error, refetch } = usePublicService(slug, serviceSlug);
  const service = data?.payload.service;
  const path = useServicePath(service?.id);

  if (isLoading) {
    return (
      <PageShell title="Service">
        <LoadingState />
      </PageShell>
    );
  }
  if (isError || !service) {
    return (
      <PageShell title="Service">
        <ErrorState message={error?.message ?? "Service not found"} onRetry={() => refetch()} />
      </PageShell>
    );
  }

  const always = service.requirements.filter((r) => r.required === "always");
  const conditional = service.requirements.filter((r) => r.required === "conditional");
  const fullPath = path.data?.payload;

  return (
    <PageShell title={service.name} description={service.summary ?? undefined}>
      <div className="mb-6 flex flex-wrap items-center gap-3 text-sm">
        <Link href={`/organizations/${service.org.slug}`} className="text-primary font-semibold hover:underline">
          {service.org.name}
        </Link>
        <VerifiedBadge />
        <ConfirmedBadge days={service.confirmed_days_ago} due={service.confirmation_due} orgName={service.org.name} />
        {service.name_am && <span className="text-muted-foreground">{service.name_am}</span>}
      </div>
      {service.upcoming_change && <UpcomingChange change={service.upcoming_change} />}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          {service.questions.length > 0 && (
            <Panel title="Check what you need" am="የሚያስፈልግዎትን ይወቁ">
              <p className="text-muted-foreground mb-4 text-sm">
                Answer a few questions and get the exact documents and steps for your situation.
              </p>
              <EligibilityCheck service={service} />
            </Panel>
          )}

          <Panel title="Requirements" am="መስፈርቶች">
            <ul>
              {always.map((r) => (
                <RequirementItem key={r.key} req={r} />
              ))}
            </ul>
            {conditional.length > 0 && (
              <>
                <p className="text-muted-foreground mt-4 text-xs font-semibold tracking-wide uppercase">Only in some cases</p>
                <ul>
                  {conditional.map((r) => (
                    <RequirementItem key={r.key} req={r} />
                  ))}
                </ul>
              </>
            )}
            {service.requirements.length === 0 && (
              <p className="text-muted-foreground text-sm">{service.no_documents_required ? "No documents are needed." : "No documents listed."}</p>
            )}
          </Panel>

          {fullPath && fullPath.steps.length > 1 && (
            <Panel title="Full path across organizations" am="ሙሉ መንገድ">
              <PathFlow path={fullPath} />
            </Panel>
          )}

          {service.steps.length > 0 && (
            <Panel title="Steps at the office" am="በቢሮው ያሉ ደረጃዎች">
              <ol className="space-y-3">
                {service.steps.map((st, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="bg-gov-yellow text-gov-ink flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-bold">
                      {i + 1}
                    </span>
                    <div>
                      <p className="font-medium">{st.title}</p>
                      <p className="text-muted-foreground text-sm">
                        {[st.location, st.estimated_minutes != null && `about ${formatMinutes(st.estimated_minutes)}`]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                      {st.description && <p className="text-sm">{st.description}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            </Panel>
          )}

          {service.common_rejection_reasons.length > 0 && (
            <Panel title="Why applications get sent back" am="ለምን ይመለሳሉ">
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {service.common_rejection_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </Panel>
          )}

          {service.branches.length > 0 && (
            <Panel title="Where and when" am="የት እና መቼ">
              <ul className="space-y-4">
                {service.branches.map((b) => (
                  <li key={b.id} className="text-sm">
                    <p className="font-semibold">
                      {b.name}
                      {b.window && <span className="bg-secondary text-primary ml-2 rounded px-1.5 py-0.5 text-xs">{b.window}</span>}
                    </p>
                    <p className="text-muted-foreground">
                      {[b.address, b.woreda && `Woreda ${b.woreda}`, b.sub_city].filter(Boolean).join(" · ")}
                    </p>
                    {b.landmark && <p className="text-muted-foreground">Landmark: {b.landmark}</p>}
                    {(b.hours_text || b.hours) && <p>Hours: {b.hours_text || b.hours}</p>}
                    {b.hours_note && <p>For this service: {b.hours_note}</p>}
                    {b.service_notes && <p className="text-muted-foreground">{b.service_notes}</p>}
                    <p className="flex flex-wrap gap-x-3">
                      {(b.service_phone || b.phone) && (
                        <a href={`tel:${(b.service_phone || b.phone)!.replace(/\s/g, "")}`} className="text-primary hover:underline">
                          {b.service_phone || b.phone}
                        </a>
                      )}
                      {b.map_url && (
                        <a href={b.map_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                          Map ↗
                        </a>
                      )}
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {service.faq.length > 0 && (
            <Panel title="Questions people ask" am="ተደጋጋሚ ጥያቄዎች">
              <dl className="space-y-3">
                {service.faq.map((f) => (
                  <div key={f.q}>
                    <dt className="font-medium">{f.q}</dt>
                    <dd className="text-muted-foreground text-sm">{f.a}</dd>
                  </div>
                ))}
              </dl>
            </Panel>
          )}
        </div>

        <aside className="space-y-4">
          <Panel title="At a glance" am="በአጭሩ">
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-muted-foreground text-xs">Fee</dt>
                {service.is_free ? (
                  <dd className="font-semibold">Free</dd>
                ) : service.fee_schedule.length > 0 ? (
                  <dd>
                    <FeeTable rows={service.fee_schedule} currency={service.fee_currency} />
                  </dd>
                ) : (
                  <dd className="font-semibold">{formatFee(service.fee_amount_min, service.fee_amount_max, service.fee_currency)}</dd>
                )}
                {service.fee_notes && <dd className="text-muted-foreground text-xs">{service.fee_notes}</dd>}
              </div>
              {(service.payment_methods.length > 0 || service.where_to_pay) && (
                <div>
                  <dt className="text-muted-foreground text-xs">How and where to pay</dt>
                  <dd>{[service.payment_methods.join(", "), service.where_to_pay].filter(Boolean).join(" · ")}</dd>
                </div>
              )}
              <div>
                <dt className="text-muted-foreground text-xs">Processing time</dt>
                <dd className="font-semibold">{service.processing_time_text || formatMinutes(service.processing_minutes)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs">How to apply</dt>
                <dd>
                  {DELIVERY[service.delivery]}
                  {service.online_url && (
                    <>
                      {" · "}
                      <a href={service.online_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                        Apply online ↗
                      </a>
                    </>
                  )}
                </dd>
                {service.online_parts && <dd className="text-muted-foreground text-xs">{service.online_parts}</dd>}
              </div>
              {service.appointment_required && (
                <div>
                  <dt className="text-muted-foreground text-xs">Appointment</dt>
                  <dd className="font-semibold">Book before you go</dd>
                  {service.appointment_how && <dd>{service.appointment_how}</dd>}
                  <dd className="flex flex-wrap gap-x-3">
                    {service.appointment_url && (
                      <a href={service.appointment_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                        Book online ↗
                      </a>
                    )}
                    {service.appointment_phone && (
                      <a href={`tel:${service.appointment_phone}`} className="text-primary hover:underline">
                        {service.appointment_phone}
                      </a>
                    )}
                  </dd>
                </div>
              )}
              {service.proxy_allowed && (
                <div>
                  <dt className="text-muted-foreground text-xs">Applying for someone else</dt>
                  <dd>{PROXY_LABEL[service.proxy_allowed]}</dd>
                  {service.proxy_notes && <dd className="text-muted-foreground text-xs">{service.proxy_notes}</dd>}
                </div>
              )}
              {service.who_can_apply && (
                <div>
                  <dt className="text-muted-foreground text-xs">Who can apply</dt>
                  <dd>{service.who_can_apply}</dd>
                </div>
              )}
              {service.audience.length > 0 && (
                <div>
                  <dt className="text-muted-foreground text-xs">For</dt>
                  <dd>{service.audience.map((a) => AUDIENCE_LABEL[a]).join(", ")}</dd>
                </div>
              )}
              {service.outputs.length > 0 && (
                <div>
                  <dt className="text-muted-foreground text-xs">You receive</dt>
                  <dd>{service.outputs.map((o) => o.name).join(", ")}</dd>
                  {service.output_validity_months && <dd className="text-xs">Valid for {service.output_validity_months} months</dd>}
                  {service.late_renewal_penalty && <dd className="text-muted-foreground text-xs">Late renewal: {service.late_renewal_penalty}</dd>}
                  {service.renewal_service && (
                    <dd className="text-xs">
                      Renew with{" "}
                      <Link href={`/organizations/${service.renewal_service.org_slug}/services/${service.renewal_service.slug}`} className="text-primary hover:underline">
                        {service.renewal_service.name}
                      </Link>
                    </dd>
                  )}
                </div>
              )}
              {service.languages.length > 0 && (
                <div>
                  <dt className="text-muted-foreground text-xs">Languages at the window</dt>
                  <dd>{service.languages.join(", ")}</dd>
                </div>
              )}
              {service.accessibility_notes && (
                <div>
                  <dt className="text-muted-foreground text-xs">Accessibility</dt>
                  <dd>{service.accessibility_notes}</dd>
                </div>
              )}
              {service.legal_basis && (
                <div>
                  <dt className="text-muted-foreground text-xs">Legal basis</dt>
                  <dd>
                    {service.legal_basis}
                    {service.legal_reference_number && ` No. ${service.legal_reference_number}`}
                  </dd>
                </div>
              )}
              {(service.contact_phone || service.contact_email) && (
                <div>
                  <dt className="text-muted-foreground text-xs">Questions about this service</dt>
                  {service.contact_name && <dd>{service.contact_name}</dd>}
                  <dd className="flex flex-wrap gap-x-3">
                    {service.contact_phone && (
                      <a href={`tel:${service.contact_phone}`} className="text-primary hover:underline">
                        {service.contact_phone}
                      </a>
                    )}
                    {service.contact_email && (
                      <a href={`mailto:${service.contact_email}`} className="text-primary hover:underline">
                        {service.contact_email}
                      </a>
                    )}
                  </dd>
                </div>
              )}
            </dl>
          </Panel>

          {service.forms.length > 0 && (
            <Panel title="Forms" am="ቅጾች">
              <ul className="space-y-1 text-sm">
                {service.forms.map((f) => (
                  <li key={f.url}>
                    <a href={apiAssetUrl(f.url) ?? f.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                      {f.title} ↗
                    </a>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <div className="bg-gov-ink rounded-md p-5 text-white">
            <p className="font-semibold">No time to queue?</p>
            <p className="mt-1 text-sm text-white/75">A verified provider can handle this service for you.</p>
            <Link
              href={`/hire?service=${encodeURIComponent(service.id)}`}
              className="bg-gov-yellow text-gov-ink mt-3 inline-block rounded-md px-4 py-2 text-sm font-semibold hover:brightness-95"
            >
              Hire a provider to do it
            </Link>
          </div>

          {service.change_log.length > 0 && (
            <Panel title="Change log" am="የለውጥ መዝገብ">
              <ul className="space-y-2 text-sm">
                {service.change_log.map((c, i) => (
                  <li key={i}>
                    <p className="text-muted-foreground text-xs">{formatDate(c.date)}</p>
                    <p>{c.summary}</p>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <ReportIssue targetType="org_service" targetId={service.id} label="Something here is wrong? Tell the organization" />
        </aside>
      </div>
    </PageShell>
  );
}
