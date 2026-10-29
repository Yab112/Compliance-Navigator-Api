"use client";

import { useRouter } from "next/navigation";
import { useWorkingService, useWorkspace } from "@cn/core/api/organizations";
import { PageShell } from "@/components/layout/page-shell";
import { useRequireAuth } from "@cn/core/hooks/use-require-auth";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";
import { ServiceForm } from "@/modules/organizations/components/service-form";

export function ServiceEditor({ orgId, serviceId }: { orgId: string; serviceId: string | null }) {
  const gate = useRequireAuth();
  const router = useRouter();
  const workspace = useWorkspace(orgId, gate === "ready");
  const working = useWorkingService(orgId, serviceId);
  const loaded = working.data?.payload.service;

  if (gate === "loading" || workspace.isLoading || (serviceId && !loaded && working.isLoading)) {
    return (
      <PageShell title="Service" maxWidth="xl">
        <LoadingState />
      </PageShell>
    );
  }
  if (workspace.isError || (serviceId && (working.isError || !loaded))) {
    return (
      <PageShell title="Service" maxWidth="xl">
        <ErrorState message={workspace.error?.message ?? working.error?.message ?? "Could not load the service"} />
      </PageShell>
    );
  }
  const org = workspace.data?.payload.organization;
  return (
    <PageShell title={loaded?.name || "New service · አዲስ አገልግሎት"} description={org?.name} maxWidth="xl">
      <ServiceForm
        orgId={orgId}
        org={org}
        serviceId={serviceId}
        loaded={loaded}
        services={workspace.data?.payload.services}
        // Point the address bar at the new service without leaving the section the person is on
        onCreated={(id) => window.history.replaceState(null, "", `/org/${orgId}/services/${id}`)}
        onExit={() => router.push(`/org/${orgId}`)}
        exitLabel="Back to dashboard"
      />
    </PageShell>
  );
}
