"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useMyOrganizations, useOrgAction, useWorkspace } from "@cn/core/api/organizations";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { useRequireAuth } from "@cn/core/hooks/use-require-auth";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { cn } from "@cn/core/lib/utils";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";
import type { MemberOrganization } from "@cn/core/types/organizations";
import { Panel } from "@cn/ui/organizations/shared";
import { OrganizationStep } from "@/modules/organizations/components/join/organization-step";
import { RepresentativeStep } from "@/modules/organizations/components/join/representative-step";
import { BranchesStep } from "@/modules/organizations/components/join/branches-step";
import { ServicesStep } from "@/modules/organizations/components/join/services-step";
import { StewardStep } from "@/modules/organizations/components/join/steward-step";
import { ReviewStep } from "@/modules/organizations/components/join/review-step";

const STEPS = [
  { title: "Organization", am: "ተቋም" },
  { title: "Representative", am: "ተወካይ" },
  { title: "Branches", am: "ቅርንጫፎች" },
  { title: "Services", am: "አገልግሎቶች" },
  { title: "Keeping it current", am: "መረጃን ማዘመን" },
  { title: "Review and submit", am: "ማጠቃለያ" },
];

const TITLE = "Register your organization · ተቋምዎን ያስመዝግቡ";

/** /organizations/join: a registration saved as a draft after every step and resumable from /org. */
export function JoinPage() {
  const gate = useRequireAuth();
  const params = useSearchParams();
  const mine = useMyOrganizations(gate === "ready");
  const orgs = mine.data?.payload.organizations ?? [];
  // Resume the draft named in the link, or the person's only unfinished registration
  const draftId = params.get("org") ?? orgs.find((o) => o.status === "draft")?.id ?? null;

  if (gate === "loading" || mine.isLoading) {
    return (
      <PageShell title={TITLE} maxWidth="xl">
        <LoadingState />
      </PageShell>
    );
  }
  return <Wizard key={draftId ?? "new"} initialOrgId={draftId} others={orgs.filter((o) => o.id !== draftId && o.status !== "draft")} />;
}

function Wizard({ initialOrgId, others }: { initialOrgId: string | null; others: MemberOrganization[] }) {
  const [orgId, setOrgId] = useState<string | null>(initialOrgId);
  const workspace = useWorkspace(orgId ?? "", !!orgId);
  const org = workspace.data?.payload.organization;
  const services = workspace.data?.payload.services ?? [];
  const action = useOrgAction();
  const [step, setStep] = useState<number | null>(initialOrgId ? null : 0);
  // Until the person picks a step, resume where they stopped
  const current = step ?? Math.min(org?.onboarding_step ?? 0, STEPS.length - 1);
  const reached = Math.max(org?.onboarding_step ?? 0, current);

  if (orgId && workspace.isLoading) {
    return (
      <PageShell title={TITLE} maxWidth="xl">
        <LoadingState />
      </PageShell>
    );
  }
  if (orgId && (workspace.isError || !org)) {
    return (
      <PageShell title={TITLE} maxWidth="xl">
        <ErrorState message={workspace.error?.message ?? "Could not load the registration"} />
      </PageShell>
    );
  }
  if (org && org.status !== "draft") {
    return (
      <PageShell title={TITLE} maxWidth="lg">
        <Panel title="This registration was sent" am="ተልኳል">
          <p className="mb-4 text-sm">{org.name} is with the platform team for verification. Keep adding and updating services from the dashboard.</p>
          <Link href={`/org/${org.id}`}>
            <Button>Go to the organization dashboard</Button>
          </Link>
        </Panel>
      </PageShell>
    );
  }

  const go = async (next: number) => {
    setStep(next);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
    // Remember the furthest step so the person can resume there later
    if (orgId && next > (org?.onboarding_step ?? 0)) {
      await action.mutateAsync({ url: apiPaths.org.workspace(orgId), method: MTD.PATCH, body: { onboarding_step: next } }).catch(() => undefined);
    }
  };

  return (
    <PageShell
      title={TITLE}
      description="Free. Tell people exactly what your services need, once. Your data appears on every path, checklist and agent job that passes through your office."
      maxWidth="xl"
    >
      {others.length > 0 && (
        <p className="bg-secondary mb-6 rounded-md px-4 py-3 text-sm">
          You already manage {others.map((o) => o.name).join(", ")}.{" "}
          <Link href="/org" className="text-primary font-semibold underline">
            Go to your organization dashboard
          </Link>
        </p>
      )}
      {org && (
        <p className="text-muted-foreground mb-4 text-sm">
          Saved as a draft after every step. You can leave and continue later from <Link href="/org" className="text-primary underline">My organization</Link>.
        </p>
      )}

      <nav aria-label="Registration steps" className="mb-6">
        <ol className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3 lg:grid-cols-6 sm:text-sm">
          {STEPS.map((s, i) => {
            const open = i <= reached && (i === 0 || !!orgId);
            return (
              <li key={s.title}>
                <button
                  type="button"
                  disabled={!open}
                  onClick={() => void go(i)}
                  aria-current={i === current ? "step" : undefined}
                  className={cn(
                    "w-full border-b-[3px] pb-2 text-left disabled:cursor-not-allowed",
                    i === current ? "border-primary text-primary font-semibold" : open ? "border-primary/40 hover:text-primary" : "border-border text-muted-foreground",
                  )}
                >
                  {i < current || (open && i !== current) ? "✓ " : ""}
                  {i + 1}. {s.title} <span className="hidden font-normal xl:inline">· {s.am}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      {current === 0 && <OrganizationStep org={org} onSaved={(id) => { setOrgId(id); void go(1); }} />}
      {current === 1 && org && <RepresentativeStep org={org} onBack={() => void go(0)} onNext={() => void go(2)} />}
      {current === 2 && org && <BranchesStep org={org} onBack={() => void go(1)} onNext={() => void go(3)} />}
      {current === 3 && org && <ServicesStep org={org} services={services} onBack={() => void go(2)} onNext={() => void go(4)} />}
      {current === 4 && org && <StewardStep org={org} onBack={() => void go(3)} onNext={() => void go(5)} />}
      {current === 5 && org && <ReviewStep org={org} onBack={() => void go(4)} onEdit={(i) => void go(i)} />}
    </PageShell>
  );
}
