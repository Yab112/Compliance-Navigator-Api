"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowLeft01Icon,
  Building03Icon,
  Briefcase01Icon,
  UserIcon,
  UserGroupIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react";
import { useFaydaStatus } from "@/api/guday";
import { useJoinMarketplace, useMyProvider } from "@/api/providers";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { ErrorState, Field, LoadingState } from "@/modules/guday/components/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { useUserStore } from "@/store";
import type { EntityType, ProviderType } from "@/types/provider";
import { VerifiedIdentityCard, VerifyStep } from "../components/fayda-step";
import { PhotoUploader } from "../components/photo-uploader";
import { EMPTY_PROVIDER_FORM, ProviderForm, cleanForm } from "../components/provider-form";
import { TYPE_META, TYPE_ORDER } from "../constants";

const ENTITY_META: Record<EntityType, { label: string; am: string; blurb: string }> = {
  individual: { label: "Individual", am: "ግለሰብ", blurb: "You work for yourself. Your Fayda-verified name is shown on your profile." },
  company: {
    label: "Company",
    am: "ድርጅት",
    blurb: "A registered business with TIN and trade licence. You verify as its representative and can add your team.",
  },
};

const TYPE_ICON: Record<ProviderType, IconSvgElement> = {
  guday_geday: Briefcase01Icon,
  agency: Building03Icon,
};
const ENTITY_ICON: Record<EntityType, IconSvgElement> = { individual: UserIcon, company: UserGroupIcon };

function Choice({ active, onClick, title, am, body, icon }: { active: boolean; onClick: () => void; title: string; am: string; body: string; icon: IconSvgElement }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={cn(
        "relative flex flex-col gap-2 rounded-xl border p-5 text-left transition",
        active ? "border-primary bg-secondary/60 ring-primary shadow-sm ring-2" : "border-border bg-card hover:border-primary/50 hover:shadow-sm",
      )}
    >
      <span className={cn("flex size-11 items-center justify-center rounded-lg", active ? "bg-primary text-white" : "bg-secondary text-primary")}>
        <HugeiconsIcon icon={icon} className="size-6" />
      </span>
      <span className="font-semibold">
        {title} <span className="text-muted-foreground text-sm font-normal">· {am}</span>
      </span>
      <span className="text-muted-foreground text-xs leading-relaxed">{body}</span>
      {active && <span className="bg-primary absolute top-3 right-3 flex size-5 items-center justify-center rounded-full text-[11px] text-white">✓</span>}
    </button>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <Button type="button" variant="outline" onClick={onClick}>
      <HugeiconsIcon icon={ArrowLeft01Icon} /> Back
    </Button>
  );
}

function FileField({ id, label, hint, accept, onFile }: { id: string; label: string; hint: string; accept: string; onFile: (f: File | null) => void }) {
  return (
    <Field label={label} htmlFor={id} hint={hint}>
      <Input id={id} type="file" accept={accept} onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
    </Field>
  );
}

export function JoinMarketplace() {
  const router = useRouter();
  const params = useSearchParams();
  const gate = useAuthGate();
  const user = useUserStore((s) => s.user);
  const mine = useMyProvider(gate === "ready");
  const fayda = useFaydaStatus(gate === "ready");
  const join = useJoinMarketplace();

  const initialType = TYPE_ORDER.includes(params.get("type") as ProviderType) ? (params.get("type") as ProviderType) : null;
  const [type, setType] = useState<ProviderType | null>(initialType);
  const [entity, setEntity] = useState<EntityType | null>((params.get("entity") as EntityType) || null);
  const [confirmed, setConfirmed] = useState(!!(initialType && params.get("entity")));
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [view, setView] = useState<1 | 2 | 3 | null>(null);
  const [formReached, setFormReached] = useState(false);
  const [licenseDoc, setLicenseDoc] = useState<File | null>(null);
  const [idDoc, setIdDoc] = useState<File | null>(null);
  const [nationalId, setNationalId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const existing = mine.data?.payload.provider;
  useEffect(() => {
    if (existing) router.replace("/me/provider");
  }, [existing, router]);

  // Keep the choice in the URL so the Fayda round trip comes back to the same step
  useEffect(() => {
    if (confirmed && type && entity) router.replace(`/providers/join?type=${type}&entity=${entity}`, { scroll: false });
  }, [confirmed, type, entity, router]);

  const status = fayda.data?.payload;
  const verification = status?.verification ?? null;
  const needsVerification = !!status?.required && !verification;
  const maxStep: 1 | 2 | 3 = !confirmed ? 1 : needsVerification ? 2 : 3;
  // The visitor can step back without losing anything; forward is limited to what is unlocked
  const step = Math.min(view ?? maxStep, maxStep) as 1 | 2 | 3;
  if (step === 3 && !formReached) setFormReached(true);
  const canOpen = (i: number) => i <= maxStep && (i !== 2 || !!status?.required);

  return (
    <PageShell
      title="Join the marketplace · ይቀላቀሉ"
      description="List yourself or your company as a Guday Geday agent or agency. Verified profiles with good reviews rise to the top, and clients can see exactly why they should trust you."
      maxWidth="lg"
    >
      {gate === "loading" || mine.isLoading || fayda.isLoading || existing ? (
        <LoadingState />
      ) : mine.isError || fayda.isError ? (
        <ErrorState message={(mine.error ?? fayda.error)?.message ?? "Could not load"} onRetry={() => { mine.refetch(); fayda.refetch(); }} />
      ) : (
        <>
          <ol className="mb-8 grid grid-cols-3 gap-2 text-xs">
            {["What you offer", "Verify identity", "Your profile"].map((label, i) => {
              const n = i + 1;
              const open = canOpen(n);
              return (
                <li key={label}>
                  <button
                    type="button"
                    disabled={!open}
                    onClick={() => setView(n as 1 | 2 | 3)}
                    aria-current={n === step ? "step" : undefined}
                    className={cn(
                      "w-full border-b-4 pb-2 text-left disabled:cursor-not-allowed",
                      n === step ? "border-primary font-semibold" : n < maxStep || (n === 3 && formReached) ? "border-primary/40 hover:border-primary" : "border-border text-muted-foreground",
                    )}
                  >
                    <span className={cn("mr-1.5 inline-flex size-5 items-center justify-center rounded-full text-[11px]", n < maxStep ? "bg-primary text-white" : n === step ? "bg-primary/15 text-primary" : "bg-muted")}>
                      {n < maxStep ? "✓" : n}
                    </span>
                    {label}
                  </button>
                </li>
              );
            })}
          </ol>

          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="mb-3 font-semibold">I am a</h2>
                <div role="radiogroup" className="grid gap-3 sm:grid-cols-3">
                  {TYPE_ORDER.map((t) => (
                    <Choice key={t} active={type === t} onClick={() => { setType(t); if (t === "agency") setEntity("company"); }}
                      title={TYPE_META[t].label} am={TYPE_META[t].am} body={TYPE_META[t].blurb} icon={TYPE_ICON[t]} />
                  ))}
                </div>
              </div>
              <div>
                <h2 className="mb-3 font-semibold">Listed as</h2>
                <div role="radiogroup" className="grid gap-3 sm:grid-cols-2">
                  {(["individual", "company"] as EntityType[]).map((e) => (
                    <Choice key={e} active={entity === e} onClick={() => setEntity(e)} title={ENTITY_META[e].label} am={ENTITY_META[e].am} body={ENTITY_META[e].blurb} icon={ENTITY_ICON[e]} />
                  ))}
                </div>
                {type === "agency" && entity === "individual" && (
                  <p className="text-muted-foreground mt-2 text-xs">Working alone as an agent? You can also list as a Guday Geday agent and join an agency later.</p>
                )}
              </div>
              <div className="flex justify-end">
                <Button
                  type="button"
                  size="lg"
                  disabled={!type || !entity}
                  onClick={() => {
                    setConfirmed(true);
                    setView(null);
                  }}
                >
                  Continue →
                </Button>
              </div>
            </div>
          )}

          {step === 2 && status && (
            <div className="space-y-6">
              {verification ? <VerifiedIdentityCard v={verification} /> : <VerifyStep mode={status.mode} />}
              <div className="flex justify-between">
                <BackButton onClick={() => setView(1)} />
                {verification && (
                  <Button type="button" size="lg" onClick={() => setView(3)}>
                    Continue →
                  </Button>
                )}
              </div>
            </div>
          )}

          {(step === 3 || formReached) && type && entity && maxStep === 3 && (
            <div className={cn("space-y-6", step !== 3 && "hidden")}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm">
                  Joining as <strong>{TYPE_META[type].label} · {ENTITY_META[entity].label}</strong>.{" "}
                  <button type="button" className="text-primary underline" onClick={() => setView(1)}>Change</button>
                </p>
                <BackButton onClick={() => setView(status?.required ? 2 : 1)} />
              </div>
              {verification && <VerifiedIdentityCard v={verification} />}
              <ProviderForm
                mode="join"
                providerType={type}
                entityType={entity}
                lockedName={entity === "individual" ? verification?.verified_name : null}
                initial={{
                  ...EMPTY_PROVIDER_FORM,
                  display_name: entity === "individual" ? verification?.verified_name ?? user?.fullname ?? "" : "",
                  email: user?.email ?? "",
                  phone: user?.phone ?? "",
                }}
                fileInputs={
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="sm:col-span-2">
                      <PhotoUploader
                        name={user?.fullname ?? "?"}
                        entity={entity}
                        previewUrl={photoPreview}
                        onSave={(file) => {
                          if (photoPreview) URL.revokeObjectURL(photoPreview);
                          setPhoto(file);
                          setPhotoPreview(URL.createObjectURL(file));
                        }}
                        onRemove={photo ? () => {
                          if (photoPreview) URL.revokeObjectURL(photoPreview);
                          setPhoto(null);
                          setPhotoPreview(null);
                        } : undefined}
                      />
                    </div>
                    {entity === "company" && (
                      <FileField id="pf-licdoc" label="Trade licence copy" hint="Required. Only staff can see it." accept="image/png,image/jpeg,image/webp,application/pdf" onFile={setLicenseDoc} />
                    )}
                    {!status?.required && (
                      <>
                        <Field label="National ID number" htmlFor="pf-nid" required>
                          <Input id="pf-nid" value={nationalId} onChange={(e) => setNationalId(e.target.value)} />
                        </Field>
                        <FileField id="pf-iddoc" label="Copy of your national ID" hint="Required. Only staff can see it." accept="image/png,image/jpeg,image/webp,application/pdf" onFile={setIdDoc} />
                      </>
                    )}
                  </div>
                }
                submitLabel="Submit for review"
                isSubmitting={submitting}
                serverError={serverError}
                onSubmit={async (values) => {
                  if (entity === "company" && !licenseDoc) {
                    setServerError("Attach a copy of the trade licence.");
                    return;
                  }
                  setSubmitting(true);
                  setServerError(null);
                  try {
                    await join(
                      { ...cleanForm(values), provider_type: type, entity_type: entity, national_id: nationalId || undefined },
                      { photo, licenseDocument: licenseDoc, idDocument: idDoc },
                    );
                    router.push("/me/provider?joined=1");
                  } catch (err) {
                    setServerError(getErrorMessage(err, "Could not submit your profile"));
                  } finally {
                    setSubmitting(false);
                  }
                }}
              />
            </div>
          )}
        </>
      )}
    </PageShell>
  );
}
