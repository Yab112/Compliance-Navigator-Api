"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  useImportServices,
  useMyOrganizations,
  useOrgAction,
  useOrgUpload,
  useRegisterOrganization,
  useRegistrationCheck,
  useWorkingService,
  useWorkspace,
  type OrgRegistrationInput,
} from "@cn/core/api/organizations";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { useRequireAuth } from "@cn/core/hooks/use-require-auth";
import { env } from "@cn/core/config/env";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { ErrorState, Field, LoadingState, NativeSelect } from "@cn/ui/guday/shared";
import { useUserStore } from "@cn/core/store/user-store";
import type { ImportReport, MemberOrganization, OrgServiceListItem } from "@cn/core/types/organizations";
import { BranchesManager } from "@/modules/organizations/components/branch-editor";
import { ServiceForm } from "@/modules/organizations/components/service-form";
import { CompletenessMeter, ORG_TYPE_OPTIONS, Panel, ServiceStatusChip } from "@cn/ui/organizations/shared";

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

function StepActions({ onBack, backLabel = "Back", next, nextLabel = "Save and continue", pending, disabled, error }: {
  onBack: () => void;
  backLabel?: string;
  next?: () => void;
  nextLabel?: string;
  pending?: boolean;
  disabled?: boolean;
  error?: string | null;
}) {
  return (
    <div className="space-y-2 pt-2">
      {error && <p className="text-destructive text-sm">{error}</p>}
      <div className="flex flex-wrap justify-between gap-3">
        <Button type="button" variant="outline" size="lg" onClick={onBack}>
          ← {backLabel}
        </Button>
        {next && (
          <Button type="button" size="lg" loading={pending} disabled={disabled} onClick={next}>
            {nextLabel} →
          </Button>
        )}
      </div>
    </div>
  );
}

const clean = (v: string | null | undefined) => (v && v.trim() ? v.trim() : null);

function OrganizationStep({ org, onSaved }: { org?: MemberOrganization; onSaved: (id: string) => void }) {
  const router = useRouter();
  const register = useRegisterOrganization();
  const action = useOrgAction();
  const upload = useOrgUpload();
  const [form, setForm] = useState({
    name: org?.name ?? "",
    name_am: org?.name_am ?? "",
    org_type: org?.org_type ?? "sub_city_office",
    sector: org?.sector ?? "",
    description: org?.description ?? "",
    phone: org?.phone ?? "",
    email: org?.email ?? "",
    website: org?.website ?? "",
    region: org?.region ?? "Addis Ababa",
    hq_address: org?.hq_address ?? "",
  });
  const [logo, setLogo] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setError(null);
    setPending(true);
    const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, k === "name" || k === "org_type" ? v.trim() : clean(v)]));
    try {
      if (org) {
        await action.mutateAsync({ url: apiPaths.org.workspace(org.id), method: MTD.PATCH, body });
        if (logo) await upload(apiPaths.org.logo(org.id), "logo", logo);
        onSaved(org.id);
      } else {
        const created = await register({ ...(body as unknown as OrgRegistrationInput), draft: true, branches: [] }, null, logo);
        onSaved(created.id);
      }
    } catch (err) {
      setError(getErrorMessage(err, "Could not save"));
    } finally {
      setPending(false);
    }
  };

  return (
    <Panel title="1. Your organization" am="ተቋምዎ">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Organization name (English)" htmlFor="name" required>
          <Input id="name" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Bole Sub-city Trade Office" />
        </Field>
        <Field label="ስም (Amharic)" htmlFor="name-am">
          <Input id="name-am" value={form.name_am} onChange={(e) => set("name_am", e.target.value)} />
        </Field>
        <Field label="Type" htmlFor="type" required>
          <NativeSelect id="type" className="h-9" value={form.org_type} onChange={(e) => set("org_type", e.target.value)}>
            {ORG_TYPE_OPTIONS.filter(([v]) => v !== "other").concat(ORG_TYPE_OPTIONS.filter(([v]) => v === "other")).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Sector" htmlFor="sector" hint="e.g. trade, tax, civil registration, land, health">
          <Input id="sector" value={form.sector} onChange={(e) => set("sector", e.target.value)} />
        </Field>
        <Field label="What does your organization do?" htmlFor="description" className="sm:col-span-2">
          <Textarea id="description" rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} />
        </Field>
        <Field label="Public phone" htmlFor="phone">
          <Input id="phone" type="tel" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
        </Field>
        <Field label="Public email" htmlFor="email">
          <Input id="email" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
        </Field>
        <Field label="Website" htmlFor="website">
          <Input id="website" type="url" placeholder="https://" value={form.website} onChange={(e) => set("website", e.target.value)} />
        </Field>
        <Field label="Region or city" htmlFor="region">
          <Input id="region" value={form.region} onChange={(e) => set("region", e.target.value)} />
        </Field>
        <Field label="Head office address" htmlFor="hq" className="sm:col-span-2">
          <Input id="hq" value={form.hq_address} onChange={(e) => set("hq_address", e.target.value)} />
        </Field>
        <Field label="Logo" htmlFor="logo" hint="Optional · JPG, PNG or WEBP, max 5 MB">
          <Input id="logo" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setLogo(e.target.files?.[0] ?? null)} />
        </Field>
      </div>
      <StepActions
        onBack={() => router.push("/organizations")}
        backLabel="Back to organizations"
        next={() => void save()}
        pending={pending}
        disabled={form.name.trim().length < 3}
        error={error}
      />
    </Panel>
  );
}

function RepresentativeStep({ org, onBack, onNext }: { org: MemberOrganization; onBack: () => void; onNext: () => void }) {
  const user = useUserStore((s) => s.user);
  const action = useOrgAction();
  const upload = useOrgUpload();
  const [form, setForm] = useState({
    representative_name: org.representative_name ?? user?.fullname ?? "",
    representative_title: org.representative_title ?? "",
    official_email: org.official_email ?? "",
  });
  const [letter, setLetter] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const valid = form.representative_name.trim().length >= 3 && form.representative_title.trim().length >= 2 && /\S+@\S+\.\S+/.test(form.official_email);

  const save = async () => {
    setError(null);
    try {
      await action.mutateAsync({ url: apiPaths.org.workspace(org.id), method: MTD.PATCH, body: form });
      if (letter) await upload(apiPaths.org.letter(org.id), "letter", letter);
      onNext();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <Panel title="2. Representative and authority" am="ተወካይ እና ሥልጣን">
      <div className="grid gap-4 sm:grid-cols-2">
        <p className="text-muted-foreground text-sm sm:col-span-2">
          We verify that the person registering may speak for the organization. Only the platform team sees these details.
        </p>
        <Field label="Your full name" htmlFor="rep-name" required>
          <Input id="rep-name" value={form.representative_name} onChange={(e) => setForm({ ...form, representative_name: e.target.value })} />
        </Field>
        <Field label="Your position" htmlFor="rep-title" required>
          <Input id="rep-title" value={form.representative_title} onChange={(e) => setForm({ ...form, representative_title: e.target.value })} placeholder="e.g. Head of customer service" />
        </Field>
        <Field label="Official work email" htmlFor="official-email" required hint="Use the organization's domain if it has one">
          <Input id="official-email" type="email" value={form.official_email} onChange={(e) => setForm({ ...form, official_email: e.target.value })} />
        </Field>
        <Field
          label="Authorization letter"
          htmlFor="letter"
          hint={org.has_authorization_letter ? "✓ Letter on file. Upload again to replace it." : "Signed and stamped letter naming you as the contact. PDF or image, max 5 MB"}
        >
          <Input id="letter" type="file" accept="application/pdf,image/png,image/jpeg" onChange={(e) => setLetter(e.target.files?.[0] ?? null)} />
        </Field>
      </div>
      <StepActions onBack={onBack} next={() => void save()} pending={action.isPending} disabled={!valid} error={error} />
    </Panel>
  );
}

function BranchesStep({ org, onBack, onNext }: { org: MemberOrganization; onBack: () => void; onNext: () => void }) {
  const branches = org.branches ?? [];
  return (
    <Panel title="3. Branches" am="ቅርንጫፎች">
      <p className="text-muted-foreground mb-4 text-sm">
        Every place where people get your services, with the exact address, a landmark, phone and weekly hours including the
        lunch break. Paths send each person to the branch in their sub-city.
      </p>
      <BranchesManager orgId={org.id} branches={branches} />
      <StepActions onBack={onBack} next={onNext} nextLabel="Continue" disabled={branches.length === 0} />
      {branches.length === 0 && <p className="text-muted-foreground mt-2 text-xs">Add at least one branch to continue.</p>}
    </Panel>
  );
}

const PATH_FIELDS: [string, string][] = [
  ["Documents to bring", "Each document, original or copy, how many, notarized or translated, how recent. This is the checklist people carry."],
  ["Fees and payment", "Every price line (citizens, foreigners, companies, urgent), how and where to pay. People arrive with the exact amount."],
  ["Branch, window and hours", "Which branch, which window, the weekly hours and lunch break. Nobody arrives at a closed office."],
  ["Processing time", "Added up across all the offices on a path, so people can plan their days."],
  ["Questions that change the list", "Renting or owning, citizen or foreigner. Each person sees only what applies to them."],
  ["Appointments and applying for someone", "Whether to book first, and whether an agent may apply with a power of attorney."],
  ["What people receive", "The document you issue and how long it's valid. Other organizations that require it link to you."],
  ["Legal basis and contact", "The proclamation or directive, and who answers questions."],
];

function ServicesStep({ org, services, onBack, onNext }: { org: MemberOrganization; services: OrgServiceListItem[]; onBack: () => void; onNext: () => void }) {
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const live = services.filter((s) => s.status !== "archived");

  if (editing) {
    return <EmbeddedEditor org={org} serviceId={editing === "new" ? null : editing} services={services} onDone={() => setEditing(null)} />;
  }
  return (
    <div className="space-y-6">
      <Panel title="4. Your services" am="አገልግሎቶችዎ">
        <details className="bg-secondary/40 mb-5 rounded-md p-4" open={live.length === 0}>
          <summary className="cursor-pointer text-sm font-semibold">What we show on a path, and why each part matters</summary>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            {PATH_FIELDS.map(([t, d]) => (
              <div key={t}>
                <dt className="text-sm font-medium">{t}</dt>
                <dd className="text-muted-foreground text-sm">{d}</dd>
              </div>
            ))}
          </dl>
        </details>
        {live.length === 0 ? (
          <p className="text-muted-foreground mb-4 text-sm">No services yet. Add them one by one, or many at once from a spreadsheet below.</p>
        ) : (
          <ul className="divide-border mb-4 divide-y">
            {live.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{s.name}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <ServiceStatusChip status={s.status} isLive={s.is_live} />
                  </div>
                  {s.completeness && <CompletenessMeter completeness={s.completeness} compact className="mt-2 max-w-md" />}
                </div>
                <Button variant="outline" onClick={() => setEditing(s.id)}>
                  Edit
                </Button>
              </li>
            ))}
          </ul>
        )}
        <Button onClick={() => setEditing("new")}>+ Add a service</Button>
      </Panel>
      <ImportPanel orgId={org.id} />
      <StepActions onBack={onBack} next={onNext} nextLabel="Continue" />
    </div>
  );
}

function EmbeddedEditor({ org, serviceId, services, onDone }: { org: MemberOrganization; serviceId: string | null; services: OrgServiceListItem[]; onDone: () => void }) {
  // Only an existing service is loaded; a new one keeps its form mounted after the first save
  const working = useWorkingService(org.id, serviceId);
  const loaded = working.data?.payload.service;
  if (serviceId && !loaded) return working.isError ? <ErrorState message={working.error?.message ?? "Could not load"} /> : <LoadingState />;
  return (
    <ServiceForm
      orgId={org.id}
      org={org}
      serviceId={serviceId}
      loaded={loaded}
      services={services}
      onExit={onDone}
      exitLabel="Back to services list"
    />
  );
}

function ImportPanel({ orgId }: { orgId: string }) {
  const importer = useImportServices(orgId);
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = async (dryRun: boolean) => {
    if (!file) return;
    setError(null);
    try {
      setReport(await importer.mutateAsync({ file, dryRun }));
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  const templateUrl = `${env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")}/${apiPaths.organizations.importTemplate}`;

  return (
    <Panel title="Add many services from a spreadsheet" am="ከተመን ሉህ ማስገባት">
      <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm">
        <li>
          <a href={templateUrl} className="text-primary font-medium underline">
            Download the template
          </a>{" "}
          and open it in Excel, LibreOffice or Google Sheets. Row 2 explains each column; row 3 is an example.
        </li>
        <li>Fill one row per service. Put several documents or steps in one cell separated by semicolons.</li>
        <li>Save as CSV (UTF-8), upload it, check the report, then add the services as drafts.</li>
      </ol>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input type="file" accept=".csv,text/csv" aria-label="Services CSV file" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setReport(null); }} />
        <Button variant="outline" disabled={!file} loading={importer.isPending && !report} onClick={() => void run(true)}>
          Check the file
        </Button>
      </div>
      {error && <p className="text-destructive mt-2 text-sm">{error}</p>}
      {report && (
        <div className="mt-4 space-y-3">
          <p className="text-sm">
            {report.dry_run ? (
              <>
                <strong>{report.ready}</strong> ready to add, <strong>{report.errors}</strong> with problems.
              </>
            ) : (
              <>
                <strong>{report.created}</strong> services added as drafts. Open each one to finish the details, then submit.
              </>
            )}
          </p>
          <ul className="divide-border max-h-80 divide-y overflow-y-auto rounded-md border text-sm">
            {report.rows.map((r) => (
              <li key={r.row} className="px-3 py-2">
                <p className={r.status === "error" ? "text-destructive font-medium" : "font-medium"}>
                  Row {r.row}: {r.name || "(no name)"} · {r.status === "ready" ? "ready" : r.status === "created" ? "added" : "not added"}
                </p>
                {r.errors.map((e) => (
                  <p key={e} className="text-destructive text-xs">✕ {e}</p>
                ))}
                {r.warnings.map((w) => (
                  <p key={w} className="text-xs text-amber-800">▲ {w}</p>
                ))}
              </li>
            ))}
          </ul>
          {report.dry_run && report.ready > 0 && (
            <Button loading={importer.isPending} onClick={() => void run(false)}>
              Add {report.ready} service{report.ready === 1 ? "" : "s"} as drafts
            </Button>
          )}
        </div>
      )}
    </Panel>
  );
}

function StewardStep({ org, onBack, onNext }: { org: MemberOrganization; onBack: () => void; onNext: () => void }) {
  const action = useOrgAction();
  const [form, setForm] = useState({
    steward_name: org.steward_name ?? "",
    steward_role: org.steward_role ?? "",
    steward_phone: org.steward_phone ?? "",
    steward_email: org.steward_email ?? "",
  });
  const [commit, setCommit] = useState(!!org.data_commitment_at);
  const [error, setError] = useState<string | null>(null);
  const valid = form.steward_name.trim().length >= 3 && (form.steward_phone.trim() || form.steward_email.trim()) && commit;

  const save = async () => {
    setError(null);
    const body = { ...Object.fromEntries(Object.entries(form).map(([k, v]) => [k, clean(v)])), data_commitment: commit };
    try {
      await action.mutateAsync({ url: apiPaths.org.workspace(org.id), method: MTD.PATCH, body });
      onNext();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <Panel title="5. Keeping your data current" am="መረጃን ወቅታዊ ማድረግ">
      <div className="space-y-4">
        <p className="text-sm">
          When a fee, a document or a window changes, people on the platform must know before they travel. Name the person who
          updates your services here. We remind them every 90 days to confirm each service is still accurate.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" htmlFor="st-name" required>
            <Input id="st-name" value={form.steward_name} onChange={(e) => setForm({ ...form, steward_name: e.target.value })} />
          </Field>
          <Field label="Role" htmlFor="st-role">
            <Input id="st-role" value={form.steward_role} onChange={(e) => setForm({ ...form, steward_role: e.target.value })} placeholder="e.g. Customer service officer" />
          </Field>
          <Field label="Phone" htmlFor="st-phone" hint="A phone or an email is required">
            <Input id="st-phone" type="tel" value={form.steward_phone} onChange={(e) => setForm({ ...form, steward_phone: e.target.value })} />
          </Field>
          <Field label="Email" htmlFor="st-email">
            <Input id="st-email" type="email" value={form.steward_email} onChange={(e) => setForm({ ...form, steward_email: e.target.value })} />
          </Field>
        </div>
        <label className="bg-secondary/50 flex items-start gap-3 rounded-md p-4 text-sm">
          <input type="checkbox" className="mt-1" checked={commit} onChange={(e) => setCommit(e.target.checked)} />
          <span>
            We will update requirements and prices here before they change, and confirm all services every 90 days.
            <span className="text-muted-foreground block">መስፈርቶችና ዋጋዎች ከመቀየራቸው በፊት እዚህ እናዘምናለን፤ በየ90 ቀኑ ሁሉንም አገልግሎቶች እናረጋግጣለን።</span>
          </span>
        </label>
      </div>
      <StepActions onBack={onBack} next={() => void save()} pending={action.isPending} disabled={!valid} error={error} />
    </Panel>
  );
}

function ReviewStep({ org, onBack, onEdit }: { org: MemberOrganization; onBack: () => void; onEdit: (step: number) => void }) {
  const router = useRouter();
  const check = useRegistrationCheck(org.id);
  const action = useOrgAction();
  const [submitServices, setSubmitServices] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const problems = check.data?.payload.problems ?? [];
  const services = (check.data?.payload.services ?? []).filter((s) => s.status !== "archived");
  const isOwner = org.my_role === "owner" || org.my_role === "admin";

  const send = async () => {
    setError(null);
    try {
      await action.mutateAsync({ url: apiPaths.org.submitRegistration(org.id), method: MTD.POST, body: { submit_services: submitServices } });
      router.push(`/org/${org.id}`);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  if (check.isLoading) return <LoadingState />;
  const summary: [string, string, number][] = [
    ["Organization", `${org.name}${org.sector ? ` · ${org.sector}` : ""}`, 0],
    ["Representative", org.representative_name ? `${org.representative_name}, ${org.representative_title ?? ""}` : "Not given", 1],
    ["Branches", `${org.branches?.length ?? 0}`, 2],
    ["Services", `${services.length}`, 3],
    ["Keeps the data current", org.steward_name ? `${org.steward_name}${org.data_commitment_at ? " · commitment given" : ""}` : "Not given", 4],
  ];

  return (
    <Panel title="6. Review and submit" am="ማጠቃለያ እና መላክ">
      <dl className="divide-border mb-5 divide-y text-sm">
        {summary.map(([label, value, step]) => (
          <div key={label} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <dt className="text-muted-foreground w-48">{label}</dt>
            <dd className="flex-1 font-medium">{value}</dd>
            <button type="button" className="text-primary text-xs hover:underline" onClick={() => onEdit(step)}>
              Change
            </button>
          </div>
        ))}
      </dl>
      {services.length > 0 && (
        <div className="mb-5">
          <p className="mb-2 text-sm font-semibold">How complete each service is</p>
          <ul className="space-y-3">
            {services.map((s) => (
              <li key={s.id}>
                <p className="text-sm">{s.name}</p>
                {s.completeness && <CompletenessMeter completeness={s.completeness} compact className="max-w-md" />}
              </li>
            ))}
          </ul>
          <label className="mt-4 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={submitServices} onChange={(e) => setSubmitServices(e.target.checked)} />
            Also send services that have the core details for review
          </label>
        </div>
      )}
      {problems.length > 0 && (
        <div className="mb-4 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-semibold">Still needed before sending:</p>
          <ul className="list-disc pl-5">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      {!isOwner && <p className="text-muted-foreground mb-2 text-sm">Only an owner of the organization can send the registration.</p>}
      <StepActions
        onBack={onBack}
        next={() => void send()}
        nextLabel="Send for verification"
        pending={action.isPending}
        disabled={problems.length > 0 || !isOwner}
        error={error}
      />
    </Panel>
  );
}
