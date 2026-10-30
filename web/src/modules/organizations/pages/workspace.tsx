"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMyOrganizations, useOrgAction, useWorkspace } from "@cn/core/api/organizations";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { useRequireAuth } from "@cn/core/hooks/use-require-auth";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { EmptyState, ErrorState, LoadingState, formatDate } from "@cn/ui/guday/shared";
import type { OrgInvite } from "@cn/core/types/organizations";
import { OrgLogo, OrgStatusChip, Panel } from "@cn/ui/organizations/shared";
import { ServicesTab } from "@/modules/organizations/components/workspace/services-tab";
import { ReportsTab } from "@/modules/organizations/components/workspace/reports-tab";
import { ProfileTab } from "@/modules/organizations/components/workspace/profile-tab";
import { BranchesTab } from "@/modules/organizations/components/workspace/branches-tab";
import { MembersTab } from "@/modules/organizations/components/workspace/members-tab";
import { InsightTab } from "@/modules/organizations/components/workspace/insight-tab";

/** /org: send members to their organization, everyone else to registration. */
export function WorkspaceIndex() {
  const gate = useRequireAuth();
  const router = useRouter();
  const mine = useMyOrganizations(gate === "ready");
  const orgs = mine.data?.payload.organizations;
  const invites = mine.data?.payload.invites ?? [];

  useEffect(() => {
    if (orgs?.length === 1 && !invites.length) router.replace(`/org/${orgs[0].id}`);
  }, [orgs, invites.length, router]);

  if (gate === "loading" || mine.isLoading || (orgs?.length === 1 && !invites.length)) {
    return (
      <PageShell title="My organization · የእኔ ተቋም" maxWidth="lg">
        <LoadingState />
      </PageShell>
    );
  }
  return (
    <PageShell title="My organization · የእኔ ተቋም" maxWidth="lg">
      {invites.length > 0 && <Invites invites={invites} />}
      {!orgs?.length ? (
        <EmptyState title="You don't manage an organization yet">
          <p className="mb-4">Register your organization to publish its services, or ask its owner to invite your email.</p>
          <Link href="/organizations/join">
            <Button>Register your organization</Button>
          </Link>
        </EmptyState>
      ) : (
        <ul className="space-y-3">
          {orgs.map((o) => (
            <li key={o.id}>
              <Link href={`/org/${o.id}`} className="border-border bg-card hover:border-primary flex items-center gap-3 rounded-md border p-4">
                <OrgLogo name={o.name} url={o.logo_url} />
                <div>
                  <p className="font-semibold">{o.name}</p>
                  <OrgStatusChip status={o.status} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PageShell>
  );
}

/** Invitations wait for the person's answer: nobody is added to an organization without agreeing. */
function Invites({ invites }: { invites: OrgInvite[] }) {
  const action = useOrgAction();
  const [err, setErr] = useState<string | null>(null);
  const answer = async (id: string, reply: "accept" | "decline") => {
    setErr(null);
    try {
      await action.mutateAsync({ url: apiPaths.organizations.invite(id, reply), method: MTD.POST });
    } catch (e) {
      setErr(getErrorMessage(e));
    }
  };
  return (
    <Panel title="Invitations" am="ግብዣዎች">
      <ul className="divide-border divide-y">
        {invites.map((i) => (
          <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
            <div className="flex min-w-0 items-center gap-3">
              <OrgLogo name={i.org_name} url={i.logo_url} />
              <div className="min-w-0">
                <p className="font-semibold break-words">{i.org_name}</p>
                <p className="text-muted-foreground text-xs">
                  Invited as {i.role === "owner" ? "an owner" : "an editor"} · {formatDate(i.created_at)}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" loading={action.isPending} onClick={() => void answer(i.id, "accept")}>
                Join
              </Button>
              <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => void answer(i.id, "decline")}>
                Decline
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {err && (
        <p role="alert" className="text-destructive mt-2 text-sm">
          {err}
        </p>
      )}
    </Panel>
  );
}

const TABS = [
  { id: "services", label: "Services · አገልግሎቶች" },
  { id: "profile", label: "Profile · መገለጫ" },
  { id: "branches", label: "Branches · ቅርንጫፎች" },
  { id: "reports", label: "Reports · ሪፖርቶች" },
  { id: "members", label: "Team · ቡድን" },
  { id: "insight", label: "Insight · ትንታኔ" },
] as const;
type Tab = (typeof TABS)[number]["id"];

const STATUS_HELP: Record<string, string> = {
  draft: "Your registration isn't finished yet. Complete the remaining steps and send it for verification.",
  pending: "We are verifying your organization. You can prepare services now; they go public once you are verified and staff approve them.",
  rejected: "Verification was not approved. Read the note, update your details and contact the platform team.",
  suspended: "Your organization is suspended and its services are hidden. Contact the platform team.",
};

export function Workspace({ orgId }: { orgId: string }) {
  const gate = useRequireAuth();
  const { data, isLoading, isError, error, refetch } = useWorkspace(orgId, gate === "ready");
  const [tab, setTab] = useState<Tab>("services");
  const org = data?.payload.organization;
  const services = data?.payload.services ?? [];

  if (gate === "loading" || isLoading) {
    return (
      <PageShell title="Organization dashboard" maxWidth="xl">
        <LoadingState />
      </PageShell>
    );
  }
  if (isError || !org) {
    return (
      <PageShell title="Organization dashboard" maxWidth="xl">
        <ErrorState message={error?.message ?? "Could not load the organization"} onRetry={() => refetch()} />
      </PageShell>
    );
  }

  return (
    <PageShell title={org.name} description="Organization dashboard · የተቋም ዳሽቦርድ" maxWidth="xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <OrgLogo name={org.name} url={org.logo_url} />
          <div>
            <OrgStatusChip status={org.status} />
            {org.status === "verified" && (
              <Link href={`/organizations/${org.slug}`} className="text-primary ml-2 text-sm hover:underline">
                View public page ↗
              </Link>
            )}
          </div>
        </div>
        <Link href={`/org/${org.id}/services/new`}>
          <Button size="lg">+ Add a service</Button>
        </Link>
      </div>
      {STATUS_HELP[org.status] && (
        <div className="mb-6 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {STATUS_HELP[org.status]}
          {org.verification_note && <p className="mt-1 font-medium">Note from staff: {org.verification_note}</p>}
          {org.status === "draft" && (
            <Link href={`/organizations/join?org=${org.id}`} className="mt-2 inline-block font-semibold underline">
              Finish registration →
            </Link>
          )}
        </div>
      )}

      <div role="tablist" className="border-border mb-6 flex gap-1 overflow-x-auto overflow-y-hidden border-b [scrollbar-width:none]">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "border-b-[3px] px-3 py-2 text-sm whitespace-nowrap",
              tab === t.id ? "border-primary text-primary font-semibold" : "text-muted-foreground border-transparent",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "services" && <ServicesTab org={org} services={services} />}
      {tab === "profile" && <ProfileTab org={org} />}
      {tab === "branches" && <BranchesTab org={org} />}
      {tab === "reports" && <ReportsTab orgId={org.id} />}
      {tab === "members" && <MembersTab org={org} />}
      {tab === "insight" && <InsightTab orgId={org.id} />}
    </PageShell>
  );
}
