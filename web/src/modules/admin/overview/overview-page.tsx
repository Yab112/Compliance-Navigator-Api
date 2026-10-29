"use client";

import Link from "next/link";
import { BarList } from "@/components/charts/bar-list";
import { LineChart } from "@/components/charts/line-chart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAdminOverview } from "@/api/admin";
import { useSupportSummary } from "@/api/support";
import { AdminPage } from "@/modules/admin/components/admin-page";
import { formatDay, humanize, timeAgo } from "@/modules/admin/shared/format";
import { StatTile } from "@/modules/admin/shared/stat-tile";
import { ErrorState, EmptyState, LoadingState } from "@/modules/admin/shared/states";
import { StatusBadge } from "@/modules/admin/shared/status-badge";
import { getErrorMessage } from "@/lib/errors";
import type { AIStatus, GraphCounts } from "@/types/admin";

const GOAL_LABELS: Record<string, string> = {
  passport: "Passport",
  kebele_id: "Kebele ID",
  tin: "TIN",
  trade_license: "Trade license",
  commercial_registration: "Commercial registration",
  fintech_license: "Fintech license",
};

function isOk<T extends object>(v: T | { error: string }): v is T {
  return !("error" in v);
}

export function OverviewPage() {
  const { payload: o, isLoading, error, refetch } = useAdminOverview();
  const support = useSupportSummary().payload?.totals;

  if (isLoading) return <AdminPage title="Overview"><LoadingState /></AdminPage>;
  if (error || !o) {
    return (
      <AdminPage title="Overview">
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      </AdminPage>
    );
  }

  const graph: GraphCounts | null = isOk(o.graph) ? o.graph : null;
  const ai: AIStatus | null = isOk(o.ai) ? o.ai : null;
  const agents = o.guday.agents;
  const cases = o.guday.cases;
  const orgs = o.organizations && !("error" in o.organizations) ? o.organizations : null;
  const openCases = (cases.open ?? 0) + (cases.requested ?? 0) + (cases.accepted ?? 0) + (cases.in_progress ?? 0);
  const pending = agents.pending ?? 0;
  const failedSources = o.dataSources.filter((s) => s.lastRun?.status === "failed").length;

  return (
    <AdminPage
      title="Overview"
      description="Live state of the Compliance Navigator platform: citizens' roadmaps, licensed Guday Geday agents, the MESOB catalog, the knowledge graph and the AI assistant."
    >
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile
          label="Support desk"
          value={support ? support.new + support.open + support.waiting_customer : "-"}
          hint={
            support
              ? `${support.overdue} overdue · ${support.unassigned} unassigned`
              : "Requests people sent to a person"
          }
          href="/admin/support"
          tone={support && (support.overdue || support.new) ? "attention" : "default"}
        />
        <StatTile label="Registered users" value={o.users.total} hint={`+${o.users.new_30d} in the last 30 days`} href="/admin/users" />
        <StatTile label="Roadmaps (30 days)" value={o.roadmaps.last_30d} hint={`${o.roadmaps.total.toLocaleString("en")} all time`} />
        <StatTile label="Approved providers" value={agents.approved ?? 0} hint={`${agents.suspended ?? 0} suspended`} href="/admin/marketplace?status=approved" />
        <StatTile
          label="Pending agent applications"
          value={pending}
          hint={pending ? "Waiting for review" : "Queue is clear"}
          href="/admin/marketplace"
          tone={pending ? "attention" : "default"}
        />
        <StatTile label="Open hires" value={openCases} hint={`${cases.completed ?? 0} completed`} href="/admin/marketplace/hires" />
        <StatTile
          label="Open feedback flags"
          value={o.openFlags}
          hint="Users reporting wrong information"
          href="/admin/feedback"
          tone={o.openFlags ? "attention" : "default"}
        />
        <StatTile
          label="Organizations"
          value={orgs?.organizations ?? "-"}
          hint={orgs ? `${orgs.verified} verified · ${orgs.live_services} live services` : "Unavailable"}
          href="/admin/organizations?status=all"
          tone={orgs?.pending_orgs ? "attention" : "default"}
        />
        <StatTile
          label="Service submissions"
          value={orgs?.pending_submissions ?? 0}
          hint={orgs?.pending_submissions ? "Waiting for review" : "Queue is clear"}
          href="/admin/submissions"
          tone={orgs?.pending_submissions ? "attention" : "default"}
        />
        <StatTile label="MESOB services" value={o.catalog.services} hint={`${o.catalog.institutions} institutions · ${o.catalog.centers} centers`} href="/admin/catalog" />
        <StatTile label="Graph nodes" value={graph?.totalNodes ?? "-"} hint={graph ? `${graph.totalRelationships.toLocaleString("en")} relationships` : "Neo4j unavailable"} href="/admin/graph" />
        <StatTile
          label="Stale documents"
          value={graph?.staleDocuments ?? "-"}
          hint="Not verified in 30 days"
          href="/admin/graph"
          tone={graph?.staleDocuments ? "attention" : "default"}
        />
        <StatTile
          label="AI assistant"
          value={ai ? humanize(ai.provider) : "-"}
          hint={ai ? `${(ai.knowledgeBase.total ?? 0).toLocaleString("en")} knowledge chunks` : "Status unavailable"}
          href="/admin/ai"
        />
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Activity, last 30 days</CardTitle>
            <CardDescription>Roadmaps generated and Guday Geday requests created per day</CardDescription>
          </CardHeader>
          <CardContent>
            <LineChart
              ariaLabel="Roadmaps and client requests per day over the last 30 days"
              labels={o.roadmapsByDay.map((d) => d.day)}
              formatLabel={formatDay}
              series={[
                { name: "Roadmaps", values: o.roadmapsByDay.map((d) => d.count) },
                { name: "Client requests", values: o.casesByDay.map((d) => d.count) },
              ]}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Roadmaps by goal</CardTitle>
            <CardDescription>What citizens are trying to get done</CardDescription>
          </CardHeader>
          <CardContent>
            {o.roadmapsByGoal.length ? (
              <BarList
                ariaLabel="Roadmaps by goal"
                data={o.roadmapsByGoal.map((g) => ({ label: GOAL_LABELS[g.goal] ?? humanize(g.goal), value: g.count }))}
              />
            ) : (
              <EmptyState title="No roadmaps yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Agents by status</CardTitle>
            <CardDescription>
              {o.guday.licensesExpiringIn30Days} license{o.guday.licensesExpiringIn30Days === 1 ? "" : "s"} expiring in 30 days
            </CardDescription>
          </CardHeader>
          <CardContent>
            {Object.keys(agents).length ? (
              <BarList
                ariaLabel="Guday Geday agents by status"
                data={(["pending", "approved", "suspended", "rejected"] as const).map((s) => ({
                  label: humanize(s),
                  value: agents[s] ?? 0,
                }))}
              />
            ) : (
              <EmptyState title="No agent applications yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Approved agents by sub-city</CardTitle>
            <CardDescription>Coverage across Addis Ababa</CardDescription>
          </CardHeader>
          <CardContent>
            {o.guday.approvedBySubCity.length ? (
              <BarList
                ariaLabel="Approved agents by sub-city"
                data={o.guday.approvedBySubCity.map((r) => ({ label: humanize(r.sub_city), value: r.c }))}
              />
            ) : (
              <EmptyState title="No approved agents yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Data source health</CardTitle>
            <CardDescription>
              {failedSources ? `${failedSources} source(s) failed on their last run` : "Last run of each pipeline"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="divide-border divide-y">
              {o.dataSources.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2 py-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{s.label}</p>
                    <p className="text-muted-foreground text-[11px]">Last run {timeAgo(s.lastRun?.started_at)}</p>
                  </div>
                  <StatusBadge status={s.lastRun?.status ?? "never run"} tone={s.lastRun ? undefined : "neutral"} />
                </li>
              ))}
            </ul>
            <Link href="/admin/data-sources" className="text-primary mt-3 inline-block text-xs underline">
              Manage data sources
            </Link>
          </CardContent>
        </Card>
      </div>
    </AdminPage>
  );
}
