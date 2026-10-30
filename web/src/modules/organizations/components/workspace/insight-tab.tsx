"use client";

import { useOrgAnalytics } from "@cn/core/api/organizations";
import { LoadingState } from "@cn/ui/guday/shared";
import { Panel } from "@cn/ui/organizations/shared";

export function InsightTab({ orgId }: { orgId: string }) {
  const { data, isLoading } = useOrgAnalytics(orgId);
  const rows = data?.payload.services ?? [];
  if (isLoading) return <LoadingState />;
  return (
    <Panel title="How people use your services" am="አጠቃቀም">
      {rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">Numbers appear once your services are live.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="text-muted-foreground text-xs">
              <tr>
                <th className="py-2 pr-3 font-medium">Service</th>
                <th className="py-2 pr-3 text-right font-medium">Page views</th>
                <th className="py-2 pr-3 text-right font-medium">Requirement checks</th>
                <th className="py-2 pr-3 text-right font-medium">Path views</th>
                <th className="py-2 text-right font-medium">Last 30 days</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.service_id} className="border-border border-t">
                  <td className="py-2 pr-3">{r.name}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{r.views}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{r.eligibility_checks}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{r.path_views}</td>
                  <td className="py-2 text-right tabular-nums">{r.last_30_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
