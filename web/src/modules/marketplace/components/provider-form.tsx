"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { ServiceMultiPicker } from "@/modules/guday/components/service-picker";
import { Field, LANGUAGE_OPTIONS, NativeSelect, PHONE_RE } from "@/modules/guday/components/shared";
import type { EntityType, FeeUnit, Provider, ProviderFormValues, ProviderService, ProviderType } from "@/types/provider";
import { AREA_OPTIONS, REGIONS, SPECIALTIES, specialtyLabel } from "../constants";
import { cleanTelegram, TELEGRAM_HINT, TELEGRAM_RE } from "@/lib/telegram";

export const EMPTY_PROVIDER_FORM: ProviderFormValues = {
  display_name: "",
  phone: "",
  service_areas: [],
  specialties: [],
  service_ids: [],
  languages: ["am"],
  experience_years: 0,
  fee_unit: "negotiable",
  highlights: [],
};

export function providerToForm(p: Provider): ProviderFormValues {
  return {
    display_name: p.display_name,
    display_name_am: p.display_name_am ?? "",
    headline: p.headline ?? "",
    bio: p.bio ?? "",
    phone: p.phone ?? "",
    telegram_username: p.telegram_username ? `@${p.telegram_username}` : "",
    email: p.email ?? "",
    website: p.website ?? "",
    address: p.address ?? "",
    service_areas: p.service_areas,
    specialties: p.specialties,
    service_ids: p.service_ids,
    languages: p.languages,
    experience_years: p.experience_years,
    fee_from: p.fee_from ?? null,
    fee_to: p.fee_to ?? null,
    fee_unit: p.fee_unit,
    pricing_notes: p.pricing_notes ?? "",
    highlights: p.highlights,
    accepting_work: p.accepting_work,
    legal_name: p.legal_name ?? "",
    tin: p.tin ?? "",
    trade_license_no: p.trade_license_no ?? "",
    representative_title: p.representative_title ?? "",
    external_license_type: p.external_license_type ?? "",
    external_license_no: p.external_license_no ?? "",
    vat_registered: p.vat_registered ?? false,
    vat_number: p.vat_number ?? "",
  };
}

/** Empty strings become null so optional fields can be cleared. */
export function cleanForm(v: ProviderFormValues): ProviderFormValues {
  const out: Record<string, unknown> = { ...v };
  for (const [k, val] of Object.entries(out)) {
    if (typeof val === "string") out[k] = val.trim() === "" ? null : val.trim();
  }
  out.highlights = v.highlights.map((h) => h.trim()).filter(Boolean);
  return out as ProviderFormValues;
}

const LICENSE_HINT: Record<ProviderType, string> = {
  guday_geday: "Optional. For example a power-of-attorney registration.",
  agency: "Customs clearing permit, travel agency licence, employment agency licence, and so on.",
};

type ProviderFormProps = {
  providerType: ProviderType;
  entityType: EntityType;
  initial: ProviderFormValues;
  initialServices?: ProviderService[];
  /** Name locked to the Fayda name for individuals */
  lockedName?: string | null;
  mode: "join" | "edit";
  fileInputs?: React.ReactNode;
  submitLabel: string;
  isSubmitting: boolean;
  serverError?: string | null;
  onSubmit: (values: ProviderFormValues) => void;
};

function CheckGrid({ options, value, onChange, idPrefix }: { options: { value: string; label: string }[]; value: string[]; onChange: (v: string[]) => void; idPrefix: string }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
      {options.map((o) => (
        <label key={o.value} htmlFor={`${idPrefix}-${o.value}`} className="flex items-center gap-2 text-xs">
          <input
            id={`${idPrefix}-${o.value}`}
            type="checkbox"
            className="accent-primary size-4"
            checked={value.includes(o.value)}
            onChange={(e) => onChange(e.target.checked ? [...value, o.value] : value.filter((x) => x !== o.value))}
          />
          {o.label}
        </label>
      ))}
    </div>
  );
}

function Legend({ n, title, am }: { n: number; title: string; am: string }) {
  return (
    <legend className="mb-3 text-sm font-semibold">
      {n}. {title} <span className="text-muted-foreground font-normal">· {am}</span>
    </legend>
  );
}

export function ProviderForm({
  providerType,
  entityType,
  initial,
  initialServices = [],
  lockedName,
  mode,
  fileInputs,
  submitLabel,
  isSubmitting,
  serverError,
  onSubmit,
}: ProviderFormProps) {
  const [v, setV] = useState<ProviderFormValues>(initial);
  const [services, setServices] = useState<ProviderService[]>(initialServices);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = <K extends keyof ProviderFormValues>(k: K, val: ProviderFormValues[K]) => setV((prev) => ({ ...prev, [k]: val }));
  const company = entityType === "company";

  const validate = () => {
    const e: Record<string, string> = {};
    if (v.display_name.trim().length < 3) e.display_name = "Enter at least 3 characters";
    if (!PHONE_RE.test(v.phone.replace(/\s/g, ""))) e.phone = "Ethiopian mobile number, for example 0911223344";
    // Clients message providers on Telegram once a job is accepted, so every provider needs one
    if (!v.telegram_username?.trim()) e.telegram_username = "Add your Telegram username so clients can message you";
    else if (!TELEGRAM_RE.test(cleanTelegram(v.telegram_username))) e.telegram_username = TELEGRAM_HINT;
    if (!v.service_areas.length) e.service_areas = "Pick at least one area";
    if (providerType === "guday_geday" && !services.length) e.service_ids = "Pick at least one service";
    if (providerType !== "guday_geday" && !v.specialties.length) e.specialties = "Pick at least one specialty";
    if (v.tin && !/^\d{10}$/.test(v.tin.trim())) e.tin = "TIN is 10 digits";
    if (company) {
      if (!v.legal_name?.trim()) e.legal_name = "Required for companies";
      if (!v.tin?.trim()) e.tin = "Required for companies";
      if (!v.trade_license_no?.trim()) e.trade_license_no = "Required for companies";
    }
    if (v.website && !/^https?:\/\//.test(v.website)) e.website = "Start with https://";
    if (v.vat_registered) {
      const vatNo = v.vat_number?.trim() ?? "";
      if (!vatNo) e.vat_number = "Enter your VAT registration number, or untick VAT registered";
      else if (!/^[0-9A-Za-z/-]{4,30}$/.test(vatNo)) e.vat_number = "4 to 30 letters, digits, / or -";
    }
    if (v.fee_from != null && v.fee_to != null && v.fee_to < v.fee_from) e.fee_to = "Must be at least the lowest fee";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  let n = 0;
  return (
    <form
      className="space-y-8"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (!validate()) return;
        onSubmit({
          ...v,
          phone: v.phone.replace(/\s/g, ""),
          telegram_username: v.telegram_username?.trim() ? cleanTelegram(v.telegram_username) : "",
          service_ids: services.map((s) => s.id),
          vat_registered: !!v.vat_registered,
          vat_number: v.vat_registered ? (v.vat_number?.trim() ?? "") : null,
        });
      }}
    >
      <fieldset>
        <Legend n={++n} title={company ? "Company" : "About you"} am={company ? "ድርጅት" : "ስለ እርስዎ"} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={company ? "Brand or display name" : "Full name"} htmlFor="pf-name" required error={errors.display_name}
            hint={lockedName ? "From your Fayda verification." : undefined}>
            <Input id="pf-name" value={v.display_name} readOnly={!!lockedName} onChange={(e) => set("display_name", e.target.value)} />
          </Field>
          <Field label="Name in Amharic" htmlFor="pf-name-am">
            <Input id="pf-name-am" value={v.display_name_am ?? ""} onChange={(e) => set("display_name_am", e.target.value)} />
          </Field>
          <Field label="Headline" htmlFor="pf-headline" hint="One line clients see first, for example: Apartments for rent in Bole" className="sm:col-span-2">
            <Input id="pf-headline" maxLength={140} value={v.headline ?? ""} onChange={(e) => set("headline", e.target.value)} />
          </Field>
          <Field label="About" htmlFor="pf-bio" hint="How you work, what you are good at, which offices you know." className="sm:col-span-2">
            <Textarea id="pf-bio" rows={4} maxLength={3000} value={v.bio ?? ""} onChange={(e) => set("bio", e.target.value)} />
          </Field>
          <Field label="Mobile phone" htmlFor="pf-phone" required error={errors.phone}>
            <Input id="pf-phone" type="tel" placeholder="09XXXXXXXX" value={v.phone} onChange={(e) => set("phone", e.target.value)} />
          </Field>
          <Field label="Telegram username" htmlFor="pf-telegram" required error={errors.telegram_username}>
            <Input id="pf-telegram" placeholder="@your_username" value={v.telegram_username ?? ""} onChange={(e) => set("telegram_username", e.target.value)} />
          </Field>
          <Field label="Email" htmlFor="pf-email">
            <Input id="pf-email" type="email" value={v.email ?? ""} onChange={(e) => set("email", e.target.value)} />
          </Field>
          {company && (
            <Field label="Website" htmlFor="pf-web" error={errors.website}>
              <Input id="pf-web" placeholder="https://" value={v.website ?? ""} onChange={(e) => set("website", e.target.value)} />
            </Field>
          )}
          <Field label="Office address" htmlFor="pf-address">
            <Input id="pf-address" value={v.address ?? ""} onChange={(e) => set("address", e.target.value)} />
          </Field>
        </div>
      </fieldset>

      <fieldset>
        <Legend n={++n} title="Work" am="ሥራ" />
        <div className="space-y-4">
          {providerType === "guday_geday" ? (
            <Field label="Services you handle" htmlFor="pf-services" required error={errors.service_ids}
              hint="Search the MESOB and organisation services you can process for clients.">
              <ServiceMultiPicker id="pf-services" value={services} onChange={setServices} />
            </Field>
          ) : (
            <div>
              <p className="mb-2 text-xs font-medium">Specialties <span className="text-destructive">*</span></p>
              <CheckGrid idPrefix="pf-spec" value={v.specialties} onChange={(x) => set("specialties", x)}
                options={SPECIALTIES[providerType].map((s) => ({ value: s, label: specialtyLabel(s) }))} />
              {errors.specialties && <p className="text-destructive mt-1 text-[11px]">{errors.specialties}</p>}
            </div>
          )}
          <div>
            <p className="mb-2 text-xs font-medium">Areas you work in <span className="text-destructive">*</span></p>
            <CheckGrid idPrefix="pf-area" value={v.service_areas} onChange={(x) => set("service_areas", x)}
              options={AREA_OPTIONS.filter((a) => !REGIONS.some((r) => r.value === a.value))} />
            <p className="text-muted-foreground mt-3 mb-2 text-[11px]">Outside Addis Ababa</p>
            <CheckGrid idPrefix="pf-region" value={v.service_areas} onChange={(x) => set("service_areas", x)} options={REGIONS} />
            {errors.service_areas && <p className="text-destructive mt-1 text-[11px]">{errors.service_areas}</p>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium">Languages</p>
              <CheckGrid idPrefix="pf-lang" value={v.languages} onChange={(x) => set("languages", x)} options={LANGUAGE_OPTIONS} />
            </div>
            <Field label="Years of experience" htmlFor="pf-exp">
              <Input id="pf-exp" type="number" min={0} max={60} value={v.experience_years}
                onChange={(e) => set("experience_years", Math.max(0, Number(e.target.value) || 0))} />
            </Field>
          </div>
          <Field label="Highlights" htmlFor="pf-highlights" hint="One per line, for example: 120+ passport files handled">
            <Textarea id="pf-highlights" rows={3} value={v.highlights.join("\n")} onChange={(e) => set("highlights", e.target.value.split("\n"))} />
          </Field>
        </div>
      </fieldset>

      <fieldset>
        <Legend n={++n} title="Pricing" am="ዋጋ" />
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="How you charge" htmlFor="pf-unit">
            <NativeSelect id="pf-unit" value={v.fee_unit} onChange={(e) => set("fee_unit", e.target.value as FeeUnit)}>
              <option value="per_job">Fixed fee per job (ETB)</option>
              <option value="percent">Commission (%)</option>
              <option value="per_hour">Per hour (ETB)</option>
              <option value="negotiable">Negotiable</option>
            </NativeSelect>
          </Field>
          <Field label={v.fee_unit === "percent" ? "Lowest %" : "Lowest fee"} htmlFor="pf-from">
            <Input id="pf-from" type="number" min={0} value={v.fee_from ?? ""}
              onChange={(e) => set("fee_from", e.target.value === "" ? null : Number(e.target.value))} />
          </Field>
          <Field label={v.fee_unit === "percent" ? "Highest %" : "Highest fee"} htmlFor="pf-to" error={errors.fee_to}>
            <Input id="pf-to" type="number" min={0} value={v.fee_to ?? ""}
              onChange={(e) => set("fee_to", e.target.value === "" ? null : Number(e.target.value))} />
          </Field>
          <Field label="Pricing notes" htmlFor="pf-pnotes" className="sm:col-span-3" hint="What is included, when you get paid. Clear pricing earns better reviews.">
            <Input id="pf-pnotes" maxLength={500} value={v.pricing_notes ?? ""} onChange={(e) => set("pricing_notes", e.target.value)} />
          </Field>
          <div className="space-y-2 sm:col-span-3">
            <label htmlFor="pf-vat" className="flex items-center gap-2 text-sm font-medium">
              <input
                id="pf-vat"
                type="checkbox"
                className="accent-primary size-4"
                checked={!!v.vat_registered}
                aria-describedby="pf-vat-hint"
                onChange={(e) => set("vat_registered", e.target.checked)}
              />
              VAT registered
            </label>
            <p id="pf-vat-hint" className="text-muted-foreground text-[11px]">
              Required by law above ETB 2 million in yearly sales; then 15% VAT is added to your price and you file it.
            </p>
            {v.vat_registered && (
              <Field label="VAT registration number" htmlFor="pf-vat-no" required error={errors.vat_number} className="sm:w-72">
                <Input id="pf-vat-no" maxLength={30} value={v.vat_number ?? ""} onChange={(e) => set("vat_number", e.target.value)} />
              </Field>
            )}
          </div>
        </div>
      </fieldset>

      <fieldset>
        <Legend n={++n} title={company ? "Registration and licences" : "Licences"} am="ፈቃድ" />
        <div className="grid gap-4 sm:grid-cols-2">
          {company && (
            <>
              <Field label="Registered legal name" htmlFor="pf-legal" required error={errors.legal_name}>
                <Input id="pf-legal" value={v.legal_name ?? ""} onChange={(e) => set("legal_name", e.target.value)} />
              </Field>
              <Field label="Trade licence number" htmlFor="pf-tl" required error={errors.trade_license_no}>
                <Input id="pf-tl" value={v.trade_license_no ?? ""} onChange={(e) => set("trade_license_no", e.target.value)} />
              </Field>
              <Field label="Your role at the company" htmlFor="pf-role" hint="You are the verified representative.">
                <Input id="pf-role" placeholder="Manager, owner..." value={v.representative_title ?? ""} onChange={(e) => set("representative_title", e.target.value)} />
              </Field>
            </>
          )}
          <Field label="TIN" htmlFor="pf-tin" required={company} error={errors.tin} hint={company ? undefined : "Optional. Adds points to your trust score."}>
            <Input id="pf-tin" inputMode="numeric" maxLength={10} value={v.tin ?? ""} onChange={(e) => set("tin", e.target.value)} />
          </Field>
          <Field label="Sector licence type" htmlFor="pf-lictype" hint={LICENSE_HINT[providerType]}>
            <Input id="pf-lictype" value={v.external_license_type ?? ""} onChange={(e) => set("external_license_type", e.target.value)} />
          </Field>
          <Field label="Sector licence number" htmlFor="pf-licno" hint="Staff check it with the issuing office before it shows as checked.">
            <Input id="pf-licno" value={v.external_license_no ?? ""} onChange={(e) => set("external_license_no", e.target.value)} />
          </Field>
        </div>
      </fieldset>

      {fileInputs && (
        <fieldset>
          <Legend n={++n} title="Documents" am="ሰነዶች" />
          {fileInputs}
        </fieldset>
      )}

      {mode === "edit" && (
        <label className={cn("flex items-center gap-2 text-sm")}>
          <input type="checkbox" className="accent-primary size-4" checked={v.accepting_work ?? true}
            onChange={(e) => set("accepting_work", e.target.checked)} />
          Accepting new work (untick to pause new requests)
        </label>
      )}

      {serverError && <p className="text-destructive text-sm">{serverError}</p>}
      <Button type="submit" size="lg" loading={isSubmitting}>{submitLabel}</Button>
    </form>
  );
}
