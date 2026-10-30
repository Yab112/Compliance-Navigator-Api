"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { HIRES_PAGE_SIZE, useMyClientRecord, useMyHires } from "@cn/core/api/providers";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { EmptyState, ErrorState, LoadingState, formatDate } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { Stars } from "@cn/ui/marketplace/trust";
import type { ClientRecord } from "@cn/core/types/provider";
import { cn } from "@cn/core/lib/utils";
import { HireRow } from "@/modules/account/components/hire-row";
import { PaymentReturnBanner } from "@/modules/account/components/payment-return-banner";

type Tab = "active" | "history";

/** What providers see about this client when a request arrives. */
function ClientRecordCard({ record }: { record: ClientRecord }) {
  const items: { label: string; value: React.ReactNode; hint?: string }[] = [
    { label: "Paid jobs", value: record.paid_jobs },
    record.hire_rate == null
      ? { label: "Hire rate", value: "New client", hint: "shown after 3 decided requests" }
      : { label: "Hire rate", value: `${record.hire_rate}%` },
    { label: "Cancelled after acceptance", value: record.cancelled_after_accept },
    {
      label: "Rating from providers",
      value: record.rating_count && record.rating_avg != null ? (
        <span className="inline-flex items-center gap-1">
          <Stars value={record.rating_avg} />
          <span className="text-muted-foreground text-xs font-normal">({record.rating_count})</span>
        </span>
      ) : (
        "No ratings yet"
      ),
    },
  ];
  if (record.member_since) items.push({ label: "Member since", value: formatDate(record.member_since) });

  return (
    <section aria-labelledby="client-record-title" className="border-border bg-card mb-5 rounded-md border p-4">
      <h2 id="client-record-title" className="text-sm font-semibold">
        Your record <span className="text-muted-foreground font-normal">· as providers see it</span>
      </h2>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-5">
        {items.map((i) => (
          <div key={i.label} className="min-w-0">
            <dt className="text-muted-foreground text-[11px]">{i.label}</dt>
            <dd className="text-sm font-semibold tabular-nums">{i.value}</dd>
            {i.hint && <dd className="text-muted-foreground text-[11px]">{i.hint}</dd>}
          </div>
        ))}
      </dl>
      <p className="text-muted-foreground mt-3 text-[11px]">
        Hire rate: of the requests providers accepted, how many you paid. Only providers you send a request to see this.
      </p>
    </section>
  );
}

export function MyRequests() {
  const gate = useAuthGate();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: Tab = params.get("tab") === "history" ? "history" : "active";
  const [page, setPage] = useUrlPage();
  const { data, isLoading, isError, error, refetch } = useMyHires(tab, page, gate === "ready");
  const result = data?.payload;
  const shown = result?.items ?? [];
  const counts = result?.counts ?? { active: 0, history: 0 };
  const record = useMyClientRecord(gate === "ready").data?.payload.record;
  const setTab = (t: Tab) => {
    const next = new URLSearchParams(params.toString());
    if (t === "history") next.set("tab", "history");
    else next.delete("tab");
    next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "active", label: "Active", count: counts.active },
    { key: "history", label: "History", count: counts.history },
  ];

  return (
    <PageShell
      title="My hires · የቀጠርኳቸው"
      description="Everyone you hired through the marketplace. You pay once the work is delivered, then leave a review so others know whom they are hiring."
      maxWidth="lg"
    >
      {gate === "ready" && <PaymentReturnBanner />}
      {gate === "loading" || isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load your hires"} onRetry={() => refetch()} />
      ) : counts.active + counts.history === 0 ? (
        <EmptyState title="No hires yet">
          <p className="mb-4">Find a verified Guday Geday agent or agency.</p>
          <Link href="/hire"><Button>Browse providers</Button></Link>
        </EmptyState>
      ) : (
        <>
          {record && <ClientRecordCard record={record} />}
          <div role="tablist" aria-label="My hires" className="border-border mb-4 flex gap-1 border-b">
            {tabs.map((t) => (
              <button
                key={t.key}
                type="button"
                role="tab"
                id={`hires-tab-${t.key}`}
                aria-selected={tab === t.key}
                aria-controls="hires-panel"
                onClick={() => setTab(t.key)}
                className={cn(
                  "-mb-px border-b-2 px-3 py-2 text-sm",
                  tab === t.key ? "border-primary text-primary font-semibold" : "text-muted-foreground hover:text-foreground border-transparent",
                )}
              >
                {t.label} <span className="tabular-nums">({t.count})</span>
              </button>
            ))}
          </div>
          <div id="hires-panel" role="tabpanel" aria-labelledby={`hires-tab-${tab}`}>
            {shown.length === 0 ? (
              tab === "active" ? (
                <EmptyState title="No active hires">
                  <p className="mb-4">Requests you send and jobs in progress appear here.</p>
                  <Link href="/hire"><Button>Browse providers</Button></Link>
                </EmptyState>
              ) : (
                <EmptyState title="No history yet">
                  <p>Closed, declined and cancelled requests appear here.</p>
                </EmptyState>
              )
            ) : (
              <>
                <ul className="space-y-3">
                  {shown.map((h) => (
                    <HireRow key={h.id} hire={h} />
                  ))}
                </ul>
                <Pager page={page} pageSize={HIRES_PAGE_SIZE} total={result?.total ?? 0} onPage={setPage} />
              </>
            )}
          </div>
        </>
      )}
      <p className="text-muted-foreground mt-6 text-sm">
        Problem with a hire that the provider can&apos;t fix?{" "}
        <Link href="/account/support" className="text-primary font-medium hover:underline">
          Write to our support team
        </Link>
        .
      </p>
    </PageShell>
  );
}
