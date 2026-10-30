"use client";

import Link from "next/link";
import { useState } from "react";
import { useCatalogCenters, useCatalogService } from "@/api/catalog";
import { apiAssetUrl } from "@cn/core/lib/api";
import { ReportIssue } from "@/components/feedback/report-issue";
import { Badge } from "@cn/ui/badge";
import { Button } from "@cn/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@cn/ui/card";
import { HireForm } from "@/modules/marketplace/components/hire-form";
import { ProviderCard } from "@/modules/marketplace/components/provider-card";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";
import { PageNav } from "@cn/ui/layout/page-nav";

export function ServiceDetail({ id }: { id: string }) {
  const { data, isLoading, isError, error, refetch } = useCatalogService(id);
  const centers = useCatalogCenters();
  const [requesting, setRequesting] = useState(false);

  if (isLoading) return <LoadingState label="Loading service…" />;
  if (isError || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <ErrorState message={error?.message ?? "Service not found"} onRetry={() => refetch()} />
        <Link href="/services" className="text-primary mt-4 inline-block text-xs underline">
          ← Back to all services
        </Link>
      </div>
    );
  }

  const { service, agents, agentCount } = data.payload;
  const inst = service.institution;
  const logo = apiAssetUrl(inst.logo_url);
  const centerList = centers.data?.payload.centers ?? [];

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <PageNav label={service.name} />

      <header className="mt-4 mb-8 flex gap-4">
        {logo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={logo} alt="" className="border-border size-14 shrink-0 border object-contain p-1" />
        )}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{service.name}</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            {inst.name}
            {inst.name_am && <> · {inst.name_am}</>}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {inst.short_name && <Badge variant="outline">{inst.short_name}</Badge>}
            <Badge variant="secondary">Available at MESOB centers</Badge>
            {service.language === "am" && <Badge variant="outline">አማርኛ</Badge>}
          </div>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card size="sm">
              <CardHeader>
                <CardTitle>Fee</CardTitle>
              </CardHeader>
              <CardContent className="text-xs leading-relaxed">
                {service.fee_text ?? "Confirm at the center"}
              </CardContent>
            </Card>
            <Card size="sm">
              <CardHeader>
                <CardTitle>Processing time</CardTitle>
              </CardHeader>
              <CardContent className="text-xs leading-relaxed">
                {service.processing_time_text ?? "Not published"}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Required documents · የሚያስፈልጉ ሰነዶች</CardTitle>
            </CardHeader>
            <CardContent>
              {service.required_documents.length === 0 ? (
                <p className="text-muted-foreground text-xs">No documents listed by MESOB.</p>
              ) : (
                <ul className="space-y-2 text-xs">
                  {service.required_documents.map((doc, i) => (
                    <li key={i} className="flex gap-2">
                      <input
                        type="checkbox"
                        id={`doc-${i}`}
                        className="mt-0.5"
                        aria-label={`I have: ${doc}`}
                      />
                      <label htmlFor={`doc-${i}`} className="leading-relaxed">
                        {doc}
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-muted-foreground mt-3 text-[11px]">
                Tick documents as you collect them. This checklist isn&apos;t saved.
              </p>
            </CardContent>
          </Card>

          <div className="flex flex-wrap gap-3 text-xs">
            {service.online_url && (
              <a href={service.online_url} target="_blank" rel="noreferrer" className="text-primary underline">
                Apply / learn more online
              </a>
            )}
            {service.source_url && (
              <a href={service.source_url} target="_blank" rel="noreferrer" className="text-primary underline">
                Official MESOB catalog
              </a>
            )}
          </div>

          <ReportIssue targetType="gov_service" targetId={service.id} />

          <section>
            <div className="mb-3 flex items-end justify-between gap-2">
              <div>
                <h2 className="text-base font-semibold">Verified agents for this service</h2>
                <p className="text-muted-foreground text-xs">
                  {agentCount > 0
                    ? `${agentCount} verified agent${agentCount === 1 ? "" : "s"} can handle this for you. Compare trust scores and reviews.`
                    : "No verified agent lists this service yet. Our staff can still assign one."}
                </p>
              </div>
              {agentCount > agents.length && (
                <Link href={`/hire?type=guday_geday&service_id=${service.id}`} className="text-primary shrink-0 text-xs underline">
                  See all {agentCount}
                </Link>
              )}
            </div>
            {agents.length > 0 && (
              <div className="mb-4 grid gap-3 sm:grid-cols-2">
                {agents.map((a) => (
                  <ProviderCard key={a.id} provider={a} />
                ))}
              </div>
            )}
            {requesting ? (
              <HireForm
                serviceId={service.id}
                defaultTitle={service.name}
                returnTo={`/services/${service.id}`}
                submitLabel="Ask staff to assign an agent"
              />
            ) : (
              <Button onClick={() => setRequesting(true)}>Ask staff to assign an agent</Button>
            )}
          </section>
        </div>

        <aside className="space-y-4">
          <Card size="sm">
            <CardHeader>
              <CardTitle>Where to go</CardTitle>
            </CardHeader>
            <CardContent className="text-xs">
              <p className="text-muted-foreground mb-3 leading-relaxed">
                Done at MESOB one-stop service centers. Bring originals and copies of every document.
              </p>
              {centers.isLoading ? (
                <p className="text-muted-foreground">Loading centers…</p>
              ) : centerList.length === 0 ? (
                <p className="text-muted-foreground">Center list unavailable.</p>
              ) : (
                <ul className="space-y-1.5">
                  {centerList.map((c) => (
                    <li key={c.id}>
                      {c.map_url ? (
                        <a href={c.map_url} target="_blank" rel="noreferrer" className="hover:underline">
                          {c.name} ↗
                        </a>
                      ) : (
                        c.name
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardTitle>Avoid unverified intermediaries</CardTitle>
            </CardHeader>
            <CardContent className="text-muted-foreground text-xs leading-relaxed">
              Hire agents with a registration number and a verified ID, and check their reviews. Official fees are
              paid at the counter. Never hand fees to anyone in the street.
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
