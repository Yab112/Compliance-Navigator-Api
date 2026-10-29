"use client";

import Link from "next/link";
import { useOrganization } from "@cn/core/api/organizations";
import { PageShell } from "@/components/layout/page-shell";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";
import { ConfirmedBadge, OrgLogo, OrgTypeLabel, Panel, VerifiedBadge, formatFee, formatMinutes } from "@cn/ui/organizations/shared";

export function OrganizationProfile({ slug }: { slug: string }) {
  const { data, isLoading, isError, error, refetch } = useOrganization(slug);
  const org = data?.payload.organization;

  if (isLoading) {
    return (
      <PageShell title="Organization">
        <LoadingState />
      </PageShell>
    );
  }
  if (isError || !org) {
    return (
      <PageShell title="Organization">
        <ErrorState message={error?.message ?? "Organization not found"} onRetry={() => refetch()} />
      </PageShell>
    );
  }

  return (
    <PageShell title={org.name} description={org.name_am ?? undefined}>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <div className="border-border bg-card flex gap-4 rounded-md border p-5">
            <OrgLogo name={org.name} url={org.logo_url} className="size-16" />
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <VerifiedBadge />
                <OrgTypeLabel type={org.org_type} />
                {org.sector && <span className="text-muted-foreground text-xs">· {org.sector}</span>}
              </div>
              {org.description && <p className="mt-3 text-sm leading-relaxed">{org.description}</p>}
            </div>
          </div>

          <Panel title="Services" am="አገልግሎቶች">
            {org.services.length === 0 ? (
              <p className="text-muted-foreground text-sm">No services published yet.</p>
            ) : (
              <ul className="divide-border divide-y">
                {org.services.map((s) => (
                  <li key={s.id} className="py-3">
                    <Link href={`/organizations/${org.slug}/services/${s.slug}`} className="text-gov-ink font-semibold hover:underline">
                      {s.name}
                    </Link>
                    {s.name_am && <span className="text-muted-foreground text-sm"> · {s.name_am}</span>}
                    {s.summary && <p className="text-muted-foreground mt-1 text-sm">{s.summary}</p>}
                    <p className="mt-1 text-xs">
                      {formatFee(s.fee_amount_min, s.fee_amount_max, s.fee_currency)} ·{" "}
                      {s.processing_time_text || formatMinutes(s.processing_minutes)}
                      {s.delivery !== "in_person" && " · available online"}
                    </p>
                    <div className="mt-1">
                      <ConfirmedBadge days={s.confirmed_days_ago} due={s.confirmation_due} orgName={org.name} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel title="Contact" am="አድራሻ">
            <dl className="space-y-2 text-sm">
              {org.phone && (
                <div>
                  <dt className="text-muted-foreground text-xs">Phone</dt>
                  <dd>
                    <a href={`tel:${org.phone}`} className="text-primary hover:underline">
                      {org.phone}
                    </a>
                  </dd>
                </div>
              )}
              {org.email && (
                <div>
                  <dt className="text-muted-foreground text-xs">Email</dt>
                  <dd>
                    <a href={`mailto:${org.email}`} className="text-primary break-all hover:underline">
                      {org.email}
                    </a>
                  </dd>
                </div>
              )}
              {org.website && (
                <div>
                  <dt className="text-muted-foreground text-xs">Website</dt>
                  <dd>
                    <a href={org.website} target="_blank" rel="noreferrer" className="text-primary break-all hover:underline">
                      {org.website}
                    </a>
                  </dd>
                </div>
              )}
              {org.hq_address && (
                <div>
                  <dt className="text-muted-foreground text-xs">Address</dt>
                  <dd>{org.hq_address}</dd>
                </div>
              )}
              {!org.phone && !org.email && !org.website && !org.hq_address && (
                <p className="text-muted-foreground text-sm">No contact details published.</p>
              )}
            </dl>
          </Panel>
          {org.branches.length > 0 && (
            <Panel title="Branches" am="ቅርንጫፎች">
              <ul className="space-y-3 text-sm">
                {org.branches.map((b) => (
                  <li key={b.id}>
                    <p className="font-medium">{b.name}</p>
                    <p className="text-muted-foreground text-xs">
                      {[b.address, b.woreda && `Woreda ${b.woreda}`, b.sub_city, b.region].filter(Boolean).join(", ")}
                    </p>
                    {(b.hours_text || b.hours) && <p className="text-xs">{b.hours_text || b.hours}</p>}
                    {b.landmark && <p className="text-muted-foreground text-xs">Landmark: {b.landmark}</p>}
                    {b.map_url && (
                      <a href={b.map_url} target="_blank" rel="noreferrer" className="text-primary text-xs hover:underline">
                        Open map ↗
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <Link href="/organizations" className="text-primary block text-center text-sm hover:underline">
            ← All organizations
          </Link>
        </aside>
      </div>
    </PageShell>
  );
}
