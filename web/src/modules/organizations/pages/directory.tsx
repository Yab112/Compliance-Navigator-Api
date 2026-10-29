"use client";

import Link from "next/link";
import { useState } from "react";
import { useOrganizations } from "@/api/organizations";
import { PageShell } from "@/components/layout/page-shell";
import { Input } from "@/components/ui/input";
import { Pager, useUrlPage } from "@/components/ui/pager";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  NativeSelect,
  useDebounced,
} from "@/modules/guday/components/shared";
import { ORG_TYPE_OPTIONS, OrgLogo, OrgTypeLabel, VerifiedBadge } from "../components/shared";

const BENEFITS = [
  {
    title: "Customers arrive prepared",
    am: "የተዘጋጁ ደንበኞች",
    body: "People see your exact requirements before they come, so fewer applications are incomplete at the window.",
  },
  {
    title: "One place to keep requirements current",
    am: "አንድ ቦታ",
    body: "Update fees, documents and steps once. Every path and agent on the platform uses the new version.",
  },
  {
    title: "Connected to other organizations",
    am: "ከሌሎች ተቋማት ጋር የተገናኘ",
    body: "When your service needs a document from another office, citizens see the full chain in the right order.",
  },
  {
    title: "Free, with demand insight",
    am: "ነፃ",
    body: "See how many people view and check each of your services, and what they ask about.",
  },
];

const PAGE_SIZE = 24;

export function OrganizationDirectory() {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useUrlPage();
  const q = useDebounced(query.trim(), 300);
  const { data, isLoading, isError, error, refetch, isFetching } = useOrganizations({
    q: q || undefined,
    type: type || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const items = data?.payload.items ?? [];
  const total = data?.payload.total ?? 0;

  return (
    <PageShell
      title="Organizations · ተቋማት"
      description="Offices, institutions and providers that publish their services here: what they offer, who can apply, the documents you need and the steps at the window."
    >
      <section className="bg-gov-ink mb-8 grid gap-6 rounded-md p-6 text-white md:p-8 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <p className="text-gov-yellow text-sm font-semibold">ተቋምዎ በካርታው ላይ አለ?</p>
          <h2 className="mt-1 text-2xl font-bold">
            Is your organization on the map? Register for free.
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-white/80">
            Government offices, banks, hospitals, universities, embassies, NGOs and private
            providers: describe your services once and every citizen, company and agent on the
            platform gets it right.
          </p>
          <Link
            href="/organizations/join"
            className="bg-gov-yellow text-gov-ink mt-5 inline-block rounded-md px-5 py-2.5 text-sm font-semibold hover:brightness-95"
          >
            Register your organization
          </Link>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2">
          {BENEFITS.map((b) => (
            <li key={b.title} className="rounded-md bg-white/5 p-4 ring-1 ring-white/10">
              <p className="font-semibold">✓ {b.title}</p>
              <p className="text-xs text-white/60">{b.am}</p>
              <p className="mt-1 text-sm text-white/75">{b.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <div className="mb-5 grid gap-2 sm:grid-cols-[1fr_240px]">
        <label htmlFor="org-search" className="sr-only">
          Search organizations
        </label>
        <Input
          id="org-search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (page) setPage(0);
          }}
          placeholder="Search by organization or service, e.g. trade license, TIN"
        />
        <NativeSelect
          aria-label="Organization type"
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            if (page) setPage(0);
          }}
          className="h-9"
        >
          <option value="">All types</option>
          {ORG_TYPE_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </NativeSelect>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState
          message={error?.message ?? "Could not load organizations"}
          onRetry={() => refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState title="No organizations match yet">
          <p>
            Is it yours?{" "}
            <Link href="/organizations/join" className="text-primary underline">
              Register it for free
            </Link>
            .
          </p>
        </EmptyState>
      ) : (
        <>
          <p className="text-muted-foreground mb-2 text-xs" aria-live="polite">
            {total} organization{total === 1 ? "" : "s"}
            {isFetching && " · updating…"}
          </p>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((o) => (
              <li key={o.id}>
                <Link
                  href={`/organizations/${o.slug}`}
                  className="border-border bg-card hover:border-primary flex h-full gap-3 rounded-md border p-4"
                >
                  <OrgLogo name={o.name} url={o.logo_url} />
                  <div className="min-w-0">
                    <p className="leading-snug font-semibold">{o.name}</p>
                    {o.name_am && <p className="text-muted-foreground text-xs">{o.name_am}</p>}
                    <OrgTypeLabel type={o.org_type} />
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                      <VerifiedBadge />
                      <span className="text-muted-foreground">
                        {o.service_count ?? 0} service{o.service_count === 1 ? "" : "s"}
                        {o.branch_count
                          ? ` · ${o.branch_count} branch${o.branch_count === 1 ? "" : "es"}`
                          : ""}
                      </span>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <Pager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
        </>
      )}
    </PageShell>
  );
}
