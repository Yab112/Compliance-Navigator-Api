"use client";

import { useState } from "react";
import { useOrgAction, useSaveService } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import {
  type MemberOrganization,
  type OrgServiceListItem,
  type ServiceInput,
  type WorkingService,
} from "@cn/core/types/organizations";
import { CompletenessMeter, Panel, ServiceStatusChip } from "@cn/ui/organizations/shared";
import { EMPTY_SERVICE, blank, fromWorking, toPayload, computeCompleteness, SECTIONS } from "@/modules/organizations/components/service-form/model";
import { AboutSection } from "@/modules/organizations/components/service-form/sections/about";
import { DocumentsSection } from "@/modules/organizations/components/service-form/sections/documents";
import { QuestionsSection } from "@/modules/organizations/components/service-form/sections/questions";
import { FeesSection } from "@/modules/organizations/components/service-form/sections/fees";
import { WhereSection } from "@/modules/organizations/components/service-form/sections/where";
import { StepsSection } from "@/modules/organizations/components/service-form/sections/steps";
import { ResultSection } from "@/modules/organizations/components/service-form/sections/result";
import { HelpSection } from "@/modules/organizations/components/service-form/sections/help";
import { ReviewSection } from "@/modules/organizations/components/service-form/sections/review";

type ServiceFormProps = {
  orgId: string;
  org: MemberOrganization | undefined;
  serviceId: string | null;
  loaded: WorkingService | undefined;
  /** Other services of this organization, for the renewal link */
  services?: OrgServiceListItem[];
  /** Called after the first save creates the service */
  onCreated?: (id: string) => void;
  /** Called after every save with the saved name, so the page title can follow it */
  onSaved?: (name: string) => void;
  onSubmitted?: () => void;
  /** Where "Back" goes from the first section (the dashboard or the wizard list) */
  onExit: () => void;
  exitLabel: string;
};

/**
 * Everything a path step shows about one service, in sections people move through with
 * Back and Next. Unsaved edits stay in the form while moving between sections.
 */
export function ServiceForm({ orgId, org, serviceId, loaded, services = [], onCreated, onSaved, onSubmitted, onExit, exitLabel }: ServiceFormProps) {
  const saveService = useSaveService(orgId);
  const action = useOrgAction();
  const [form, setForm] = useState<ServiceInput>(() => (loaded ? fromWorking(loaded) : EMPTY_SERVICE));
  const [id, setId] = useState<string | null>(serviceId);
  const [status, setStatus] = useState(loaded?.status);
  const [isLive, setIsLive] = useState(!!loaded?.is_live);
  const [section, setSection] = useState(0);
  const [visited, setVisited] = useState(0);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [change, setChange] = useState({ change_summary: "", change_reason: "", effective_at: "" });

  const set = (patch: Partial<ServiceInput>) => setForm((f) => ({ ...f, ...patch }));
  const completeness = computeCompleteness(form);
  const branches = org?.branches ?? [];
  const canSave = form.name.trim().length >= 3;

  const go = (i: number) => {
    setSection(i);
    setVisited((v) => Math.max(v, i));
    setMsg(null);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const save = async (): Promise<string | null> => {
    setMsg(null);
    try {
      const saved = await saveService.mutateAsync({ serviceId: id, body: toPayload(form) });
      setForm(fromWorking(saved));
      setStatus(saved.status);
      setIsLive(saved.is_live);
      onSaved?.(saved.name);
      if (!id) {
        setId(saved.id);
        onCreated?.(saved.id);
      }
      setMsg({ ok: true, text: "Draft saved." });
      return saved.id;
    } catch (err) {
      setMsg({ ok: false, text: getErrorMessage(err, "Could not save") });
      return null;
    }
  };

  const submit = async () => {
    const savedId = await save();
    if (!savedId) return;
    try {
      await action.mutateAsync({
        url: apiPaths.org.submit(orgId, savedId),
        method: MTD.POST,
        body: isLive
          ? { change_summary: change.change_summary.trim(), change_reason: blank(change.change_reason), effective_at: change.effective_at || null }
          : undefined,
      });
      setStatus("submitted");
      setMsg({ ok: true, text: "Submitted. The platform team reviews it before it goes live." });
      onSubmitted?.();
    } catch (err) {
      setMsg({ ok: false, text: getErrorMessage(err) });
    }
  };

  const current = SECTIONS[section];

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
      <aside className="space-y-4 lg:sticky lg:top-[calc(var(--nav-h)+1rem)] lg:self-start">
        <div className="border-border bg-card rounded-md border p-3">
          <p className="mb-2 text-xs font-semibold">Path data filled in</p>
          <CompletenessMeter completeness={completeness} compact />
          {status && <div className="mt-2"><ServiceStatusChip status={status} isLive={isLive} /></div>}
        </div>
        <nav aria-label="Service sections">
          <ol className="space-y-1 text-sm">
            {SECTIONS.map((s, i) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => go(i)}
                  disabled={i > visited && !id}
                  aria-current={i === section ? "step" : undefined}
                  className={cn(
                    "w-full rounded-md px-2 py-1.5 text-left disabled:opacity-50",
                    i === section ? "bg-secondary text-primary font-semibold" : "hover:bg-muted",
                  )}
                >
                  {i + 1}. {s.title}
                </button>
              </li>
            ))}
          </ol>
        </nav>
      </aside>

      <div className="min-w-0 space-y-4">
        {status === "changes_requested" && loaded?.admin_note && (
          <p className="rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">The platform team asked for changes: {loaded.admin_note}</p>
        )}
        <Panel title={`${section + 1}. ${current.title}`} am={current.am}>
          {current.id === "about" && <AboutSection form={form} set={set} />}
          {current.id === "documents" && <DocumentsSection form={form} set={set} />}
          {current.id === "questions" && <QuestionsSection form={form} set={set} />}
          {current.id === "fees" && <FeesSection form={form} set={set} />}
          {current.id === "where" && <WhereSection form={form} set={set} branches={branches} orgId={orgId} />}
          {current.id === "steps" && <StepsSection form={form} set={set} />}
          {current.id === "result" && <ResultSection form={form} set={set} services={services.filter((s) => s.id !== id)} />}
          {current.id === "help" && <HelpSection form={form} set={set} orgId={orgId} />}
          {current.id === "review" && (
            <ReviewSection
              completeness={completeness}
              isLive={isLive}
              status={status}
              change={change}
              setChange={setChange}
              liveUrl={isLive && org && loaded ? `/organizations/${org.slug}/services/${loaded.slug}` : null}
            />
          )}
        </Panel>

        <div className="border-border bg-card sticky bottom-0 z-10 flex flex-wrap items-center gap-3 border-t py-3">
          <Button type="button" variant="outline" size="lg" onClick={() => (section === 0 ? onExit() : go(section - 1))}>
            ← {section === 0 ? exitLabel : "Back"}
          </Button>
          <Button type="button" variant="outline" size="lg" loading={saveService.isPending} onClick={() => void save()} disabled={!canSave}>
            Save draft
          </Button>
          {section < SECTIONS.length - 1 ? (
            <Button type="button" size="lg" disabled={!canSave} onClick={() => go(section + 1)}>
              Next: {SECTIONS[section + 1].title} →
            </Button>
          ) : (
            <Button
              type="button"
              size="lg"
              loading={action.isPending}
              onClick={() => void submit()}
              disabled={!canSave || status === "submitted" || (isLive && change.change_summary.trim().length < 5)}
            >
              {status === "submitted" ? "Waiting for review" : isLive ? "Submit the change" : "Submit for review"}
            </Button>
          )}
          {id && status !== "archived" && section === SECTIONS.length - 1 && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => action.mutateAsync({ url: apiPaths.org.archive(orgId, id), method: MTD.POST }).then(onExit)}
            >
              Archive service
            </Button>
          )}
          {msg && <p className={msg.ok ? "text-primary text-sm" : "text-destructive text-sm"}>{msg.text}</p>}
        </div>
      </div>
    </div>
  );
}

export { EMPTY_SERVICE, computeCompleteness } from "@/modules/organizations/components/service-form/model";
