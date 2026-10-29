"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  useMyOrganizations,
  useOrgAction,
  useOrgAnalytics,
  useOrgReports,
  useOrgUpload,
  useWorkspace,
} from "@cn/core/api/organizations";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { useRequireAuth } from "@cn/core/hooks/use-require-auth";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { EmptyState, ErrorState, Field, LoadingState, NativeSelect, formatDate } from "@cn/ui/guday/shared";
import type { MemberOrganization, OrgInvite, OrgReport, OrgServiceListItem } from "@cn/core/types/organizations";
import { BranchesManager } from "@/modules/organizations/components/branch-editor";
import { CompletenessMeter, ORG_TYPE_OPTIONS, OrgLogo, OrgStatusChip, Panel, ServiceStatusChip } from "@cn/ui/organizations/shared";

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

function ServicesTab({ org, services }: { org: MemberOrganization; services: OrgServiceListItem[] }) {
  const action = useOrgAction();
  const [msg, setMsg] = useState<string | null>(null);
  if (!services.length) {
    return (
      <EmptyState title="No services yet">
        <p className="mb-4">
          Describe each service people come to you for: documents to bring, fees, branches and windows, the questions that
          change the list, and the steps at the office. Add them one by one or import a spreadsheet during registration.
        </p>
        <Link href={`/org/${org.id}/services/new`}>
          <Button>Add your first service</Button>
        </Link>
      </EmptyState>
    );
  }
  const due = services.filter((s) => s.confirmation_due);
  const confirm = async (url: string) => {
    setMsg(null);
    try {
      const res = await action.mutateAsync({ url, method: MTD.POST });
      setMsg(`Confirmed ${(res as { confirmed?: number }).confirmed ?? 1} service(s). Thank you.`);
    } catch (e) {
      setMsg(getErrorMessage(e));
    }
  };
  return (
    <div className="space-y-4">
      {due.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span>
            {due.length} live service{due.length === 1 ? " is" : "s are"} due for the 90-day check. If nothing changed, confirm
            they are still accurate. If something changed, edit the service.
          </span>
          <Button size="sm" loading={action.isPending} onClick={() => void confirm(apiPaths.org.confirmAll(org.id))}>
            Confirm all are still accurate
          </Button>
        </div>
      )}
      {msg && <p className="text-primary text-sm">{msg}</p>}
      <ul className="border-border bg-card divide-border divide-y rounded-md border">
        {services.map((s) => (
          <li key={s.id} className="flex flex-wrap items-start justify-between gap-3 p-4">
            <div className="min-w-0 flex-1">
              <Link href={`/org/${org.id}/services/${s.id}`} className="text-gov-ink font-semibold hover:underline">
                {s.name}
              </Link>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <ServiceStatusChip status={s.status} isLive={s.is_live} />
                <span className="text-muted-foreground text-xs">
                  {s.version ? `Version ${s.version} · ` : ""}updated {formatDate(s.updated_at)}
                </span>
                {s.is_live && (
                  <span className={cn("text-xs", s.confirmation_due ? "font-semibold text-amber-800" : "text-muted-foreground")}>
                    {s.confirmed_days_ago == null ? "Never confirmed" : `Confirmed ${s.confirmed_days_ago} days ago`}
                  </span>
                )}
              </div>
              {s.scheduled_change && (
                <p className="mt-1 text-sm text-sky-900">
                  Approved change from {formatDate(s.scheduled_change.effective_at)}: {s.scheduled_change.summary}
                </p>
              )}
              {s.status === "changes_requested" && s.admin_note && <p className="mt-1 text-sm text-amber-800">The platform team asked: {s.admin_note}</p>}
              {s.completeness && <CompletenessMeter completeness={s.completeness} compact className="mt-2 max-w-md" />}
            </div>
            <div className="flex gap-2">
              {s.is_live && (
                <Button variant="outline" size="sm" onClick={() => void confirm(apiPaths.org.confirm(org.id, s.id))}>
                  Still accurate
                </Button>
              )}
              <Link href={`/org/${org.id}/services/${s.id}`}>
                <Button variant="outline" size="sm">
                  Edit
                </Button>
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ReportsTab({ orgId }: { orgId: string }) {
  const { data, isLoading } = useOrgReports(orgId);
  const reports = data?.payload.reports ?? [];
  if (isLoading) return <LoadingState />;
  return (
    <Panel title="Reports from the public" am="ከሕዝብ የመጡ ሪፖርቶች">
      <p className="text-muted-foreground mb-4 text-sm">
        People who found something wrong on your service pages. Fix the service if needed, then reply. Your reply goes to the platform
        team, who check it and close the report.
      </p>
      {reports.length === 0 ? (
        <p className="text-muted-foreground text-sm">No reports right now.</p>
      ) : (
        <ul className="divide-border divide-y">
          {reports.map((r) => (
            <ReportItem key={r.id} orgId={orgId} report={r} />
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ReportItem({ orgId, report }: { orgId: string; report: OrgReport }) {
  const action = useOrgAction();
  const [reply, setReply] = useState(report.org_response ?? "");
  const [err, setErr] = useState<string | null>(null);
  const respond = async (verdict: "fixed" | "correct") => {
    setErr(null);
    try {
      await action.mutateAsync({ url: apiPaths.org.report(orgId, report.id), method: MTD.POST, body: { verdict, response: reply.trim() } });
    } catch (e) {
      setErr(getErrorMessage(e));
    }
  };
  return (
    <li className="space-y-2 py-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={cn("rounded px-2 py-0.5 font-medium", report.status === "open" ? "bg-amber-100 text-amber-900" : "bg-muted")}>
          {report.status === "open" ? (report.org_response ? "answered, waiting for staff" : "open") : report.status === "resolved" ? "closed, fixed" : "closed"}
        </span>
        <span className="font-medium">{report.service_name ?? "Service"}</span>
        <span className="text-muted-foreground">{formatDate(report.created_at)}</span>
      </div>
      <p className="text-sm">“{report.message}”</p>
      {report.status === "open" ? (
        <div className="space-y-2">
          {report.org_response && (
            <p className="text-muted-foreground text-sm">
              You said {report.org_verdict === "fixed" ? "it is fixed" : "the information is correct"}: {report.org_response}. You can change your reply
              until staff close the report.
            </p>
          )}
          <Textarea rows={2} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="What you checked or changed" aria-label="Reply" />
          <div className="flex flex-wrap gap-2">
            <Button size="sm" disabled={reply.trim().length < 2} loading={action.isPending} onClick={() => void respond("fixed")}>
              We fixed it
            </Button>
            <Button size="sm" variant="outline" disabled={reply.trim().length < 2 || action.isPending} onClick={() => void respond("correct")}>
              Information is correct
            </Button>
          </div>
        </div>
      ) : (
        <>
          {report.org_response && <p className="text-muted-foreground text-sm">Your reply: {report.org_response}</p>}
          {report.resolution_note && <p className="text-muted-foreground text-sm">Platform team: {report.resolution_note}</p>}
        </>
      )}
      {err && <p className="text-destructive text-xs">{err}</p>}
    </li>
  );
}

function ProfileTab({ org }: { org: MemberOrganization }) {
  const action = useOrgAction();
  const upload = useOrgUpload();
  const [form, setForm] = useState({
    name: org.name,
    name_am: org.name_am ?? "",
    org_type: org.org_type,
    sector: org.sector ?? "",
    description: org.description ?? "",
    phone: org.phone ?? "",
    email: org.email ?? "",
    website: org.website ?? "",
    hq_address: org.hq_address ?? "",
    region: org.region ?? "",
    representative_name: org.representative_name ?? "",
    representative_title: org.representative_title ?? "",
    official_email: org.official_email ?? "",
    steward_name: org.steward_name ?? "",
    steward_role: org.steward_role ?? "",
    steward_phone: org.steward_phone ?? "",
    steward_email: org.steward_email ?? "",
  });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const text = (k: keyof typeof form, label: string, extra?: React.ComponentProps<typeof Input>) => (
    <Field label={label} htmlFor={`p-${k}`}>
      <Input id={`p-${k}`} value={form[k]} onChange={(e) => set(k, e.target.value)} {...extra} />
    </Field>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <Panel title="Organization details" am="የተቋም መረጃ">
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={async (e) => {
            e.preventDefault();
            setMsg(null);
            const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]));
            try {
              await action.mutateAsync({ url: apiPaths.org.workspace(org.id), method: MTD.PATCH, body });
              setMsg({ ok: true, text: "Saved." });
            } catch (err) {
              setMsg({ ok: false, text: getErrorMessage(err) });
            }
          }}
        >
          {text("name", "Name (English)")}
          {text("name_am", "ስም (Amharic)")}
          <Field label="Type" htmlFor="p-type">
            <NativeSelect id="p-type" className="h-9" value={form.org_type} onChange={(e) => set("org_type", e.target.value)}>
              {ORG_TYPE_OPTIONS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </NativeSelect>
          </Field>
          {text("sector", "Sector")}
          <Field label="Description" htmlFor="p-desc" className="sm:col-span-2">
            <Textarea id="p-desc" rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} />
          </Field>
          {text("phone", "Public phone", { type: "tel" })}
          {text("email", "Public email", { type: "email" })}
          {text("website", "Website", { type: "url" })}
          {text("region", "Region / city")}
          {text("hq_address", "Head office address")}
          {text("representative_name", "Representative")}
          {text("representative_title", "Representative's position")}
          {text("official_email", "Official email", { type: "email" })}
          <p className="text-xs font-semibold sm:col-span-2">Who keeps your service data current</p>
          {text("steward_name", "Name")}
          {text("steward_role", "Role")}
          {text("steward_phone", "Phone", { type: "tel" })}
          {text("steward_email", "Email", { type: "email" })}
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" loading={action.isPending}>
              Save details
            </Button>
            {msg && <p className={msg.ok ? "text-primary text-sm" : "text-destructive text-sm"}>{msg.text}</p>}
          </div>
          <p className="text-muted-foreground text-xs sm:col-span-2">
            Changing the name or type of a verified organization sends it back for verification.
          </p>
        </form>
      </Panel>
      <div className="space-y-4">
        <Panel title="Logo">
          <OrgLogo name={org.name} url={org.logo_url} className="mb-3 size-20" />
          <Input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label="Upload logo"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) await upload(apiPaths.org.logo(org.id), "logo", file);
            }}
          />
        </Panel>
        <Panel title="Authorization letter">
          <p className="mb-3 text-sm">
            {org.has_authorization_letter ? "✓ Letter on file. Upload again to replace it." : "No letter uploaded yet. It speeds up verification."}
          </p>
          <Input
            type="file"
            accept="application/pdf,image/png,image/jpeg"
            aria-label="Upload authorization letter"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) await upload(apiPaths.org.letter(org.id), "letter", file);
            }}
          />
        </Panel>
      </div>
    </div>
  );
}

function BranchesTab({ org }: { org: MemberOrganization }) {
  return (
    <Panel title="Branches" am="ቅርንጫፎች">
      <BranchesManager orgId={org.id} branches={org.branches ?? []} />
    </Panel>
  );
}

function MembersTab({ org }: { org: MemberOrganization }) {
  const action = useOrgAction();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"editor" | "owner">("editor");
  const [err, setErr] = useState<string | null>(null);
  const isOwner = org.my_role === "owner" || org.my_role === "admin";

  return (
    <Panel title="Team" am="ቡድን">
      <ul className="divide-border mb-4 divide-y">
        {(org.members ?? []).map((m) => (
          <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
            <div>
              <p className="font-medium break-words">{m.fullname || m.email}</p>
              <p className="text-muted-foreground text-xs">
                {m.email} · {m.role}
                {!m.accepted && " · invited, joins once they accept"}
              </p>
            </div>
            {isOwner && (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  action
                    .mutateAsync({ url: apiPaths.org.member(org.id, m.id), method: MTD.DELETE })
                    .catch((e) => setErr(getErrorMessage(e)))
                }
              >
                Remove
              </Button>
            )}
          </li>
        ))}
      </ul>
      {isOwner ? (
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={async (e) => {
            e.preventDefault();
            setErr(null);
            try {
              await action.mutateAsync({ url: apiPaths.org.members(org.id), method: MTD.POST, body: { email, role } });
              setEmail("");
            } catch (ex) {
              setErr(getErrorMessage(ex));
            }
          }}
        >
          <Input type="email" required placeholder="colleague@office.gov.et" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email to invite" />
          <NativeSelect className="h-9 sm:w-36" value={role} onChange={(e) => setRole(e.target.value as "editor" | "owner")} aria-label="Role">
            <option value="editor">Editor</option>
            <option value="owner">Owner</option>
          </NativeSelect>
          <Button type="submit" loading={action.isPending}>
            Invite
          </Button>
        </form>
      ) : (
        <p className="text-muted-foreground text-sm">Only owners can invite or remove team members.</p>
      )}
      {err && <p className="text-destructive mt-2 text-sm">{err}</p>}
    </Panel>
  );
}

function InsightTab({ orgId }: { orgId: string }) {
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
