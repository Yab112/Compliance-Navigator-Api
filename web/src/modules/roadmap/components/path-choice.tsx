"use client";

import Link from "next/link";
import { useState } from "react";
import { useGoalService } from "@/api/catalog";
import { useCreateHire } from "@/api/providers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import {
  Field,
  LoadingState,
  PHONE_RE,
  subCityLabel,
} from "@/modules/guday/components/shared";
import { RatingSummary, ScoreBadge, VerificationBadges } from "@/modules/marketplace/components/trust";
import { TYPE_META } from "@/modules/marketplace/constants";
import { useUserStore } from "@/store";
import type { Hire } from "@/types/provider";
import { ProviderAvatar, verifiedLevel } from "@/modules/marketplace/components/provider-avatar";

export type PathChoiceValue = "self" | "agent";

type PathChoiceProps = {
  goal: string;
  goalLabel: string;
  subCity: string;
  heldLabels: string[];
  choice: PathChoiceValue | null;
  onChoose: (choice: PathChoiceValue) => void;
  onBack: () => void;
  /** Generate the step-by-step roadmap (the "do it myself" path) */
  onShowSteps: () => void;
  isGenerating: boolean;
  generateError?: string | null;
  /** Where to come back to after signing in, with the choice preserved */
  returnTo: string;
};

const ANY_AGENT = "any";

/** Two ways forward once the user has said what they need: do it themselves, or hire an agent. */
export function PathChoice(props: PathChoiceProps) {
  const { choice, onChoose, onBack, goalLabel, subCity } = props;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-muted-foreground text-xs">
            {goalLabel} · {subCityLabel(subCity)}
          </p>
          <h2 className="text-gov-ink text-xl font-bold">How do you want to get it done?</h2>
          <p className="text-muted-foreground text-sm">እንዴት ማከናወን ይፈልጋሉ?</p>
        </div>
        <button type="button" onClick={onBack} className="text-primary text-sm font-medium hover:underline">
          ← Change details
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="How to get it done">
        <ChoiceCard
          active={choice === "self"}
          onClick={() => onChoose("self")}
          title="I'll do it myself"
          am="ራሴ እሰራዋለሁ"
          badge="Free"
          body="Get the step-by-step path: which office first, what to bring, fees and processing times."
        />
        <ChoiceCard
          active={choice === "agent"}
          onClick={() => onChoose("agent")}
          title="Hire a Guday Geday agent"
          am="ጉዳይ ገዳይ ይቅጠሩ"
          badge="Verified agents"
          body="A licensed, ID-verified agent handles the offices and queues for you. You agree the fee with the agent."
        />
      </div>

      {choice === "self" && (
        <div className="border-border bg-card space-y-3 rounded-md border p-5">
          <p className="text-sm">
            We&apos;ll build your path for <strong>{goalLabel}</strong> in {subCityLabel(subCity)}
            {props.heldLabels.length > 0 && <>, skipping what you already have ({props.heldLabels.join(", ")})</>}.
          </p>
          {props.generateError && <p className="text-destructive text-sm">{props.generateError}</p>}
          <Button size="lg" className="h-11 w-full text-base sm:w-auto" loading={props.isGenerating} onClick={props.onShowSteps}>
            Show my path →
          </Button>
        </div>
      )}

      {choice === "agent" && <HireAgent {...props} />}
    </div>
  );
}

function ChoiceCard({
  active,
  onClick,
  title,
  am,
  badge,
  body,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  am: string;
  badge: string;
  body: string;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={cn(
        "flex flex-col items-start gap-2 rounded-md border-2 p-5 text-left transition-colors",
        "focus-visible:ring-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
        active ? "border-primary bg-secondary/60" : "border-border bg-card hover:border-primary/50",
      )}
    >
      <span className="flex w-full items-center justify-between gap-2">
        <span
          className={cn(
            "flex size-5 shrink-0 items-center justify-center rounded-full border-2",
            active ? "border-primary" : "border-muted-foreground/40",
          )}
          aria-hidden
        >
          {active && <span className="bg-primary size-2.5 rounded-full" />}
        </span>
        <span className="bg-gov-yellow/30 text-gov-ink rounded px-2 py-0.5 text-[11px] font-semibold">{badge}</span>
      </span>
      <span className="text-base font-semibold">{title}</span>
      <span className="text-muted-foreground -mt-1.5 text-xs">{am}</span>
      <span className="text-muted-foreground text-sm leading-relaxed">{body}</span>
    </button>
  );
}

function HireAgent({ goal, goalLabel, subCity, heldLabels, returnTo, onShowSteps, isGenerating }: PathChoiceProps) {
  const user = useUserStore((s) => s.user);
  const { data, isLoading, isError } = useGoalService(goal, subCity);
  const payload = data?.payload;
  const service = payload?.service ?? null;
  const [agentId, setAgentId] = useState<string>(ANY_AGENT);
  const [name, setName] = useState(user?.fullname ?? "");
  const [phone, setPhone] = useState("");
  const [details, setDetails] = useState(
    `I need: ${goalLabel}.` + (heldLabels.length ? ` I already have: ${heldLabels.join(", ")}.` : ""),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [created, setCreated] = useState<Hire | null>(null);
  const { createHire, isCreating } = useCreateHire();

  if (isLoading) return <LoadingState label="Finding agents…" />;
  if (isError || !payload) return <p className="text-destructive text-sm">Could not load agents. Try again.</p>;

  if (!service) {
    return (
      <div className="border-border bg-card rounded-md border p-5 text-sm">
        <p className="font-medium">Agents can&apos;t take {goalLabel} requests online yet.</p>
        <p className="text-muted-foreground mt-1">
          This service isn&apos;t in the MESOB catalog, so it&apos;s handled at your kebele or sub-city office.
          You can still browse agents and contact one directly.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href={`/hire?type=guday_geday&area=${subCity}`}>
            <Button variant="outline">Browse agents</Button>
          </Link>
          <Button onClick={onShowSteps} loading={isGenerating}>
            Show me the steps instead
          </Button>
        </div>
      </div>
    );
  }

  if (created) {
    return (
      <div className="border-primary/40 bg-secondary/60 space-y-3 rounded-md border p-5">
        <p className="text-primary font-semibold">Request sent ✓ · ጥያቄዎ ተልኳል</p>
        <p className="text-sm">
          {created.provider_name
            ? `${created.provider_name} will accept the job and call you on ${created.client_phone}.`
            : "Our staff will assign a verified agent who will call you shortly."}
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/account/requests">
            <Button>Track my request</Button>
          </Link>
          <Button variant="outline" onClick={onShowSteps} loading={isGenerating}>
            Also show me the steps
          </Button>
        </div>
      </div>
    );
  }

  const agents = payload.agents;

  const submit = async () => {
    const next: Record<string, string> = {};
    if (name.trim().length < 2) next.name = "Enter your name";
    if (!PHONE_RE.test(phone.replace(/\s/g, ""))) next.phone = "Use an Ethiopian mobile number, e.g. 0911223344";
    setErrors(next);
    if (Object.keys(next).length) return;
    setSubmitError(null);
    try {
      const res = await createHire({
        service_id: service.id,
        provider_id: agentId === ANY_AGENT ? undefined : agentId,
        title: `${goalLabel}: ${service.name}`,
        client_name: name.trim(),
        client_phone: phone.replace(/\s/g, ""),
        sub_city: subCity,
        details: details.trim() || undefined,
      });
      setCreated(res.hire);
    } catch (err) {
      setSubmitError(getErrorMessage(err, "Could not send your request"));
    }
  };

  return (
    <div className="space-y-5">
      <div className="border-border bg-card rounded-md border p-4 text-sm">
        <p className="text-muted-foreground text-xs">MESOB service</p>
        <p className="font-medium">{service.name}</p>
        <p className="text-muted-foreground text-xs">
          {service.institution?.short_name ?? service.institution_short_name}
          {service.fee_text ? ` · official fee ${service.fee_text}` : ""}
          {service.processing_time_text ? ` · ${service.processing_time_text}` : ""}
        </p>
      </div>

      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-semibold">
          Choose an agent{" "}
          <span className="text-muted-foreground font-normal">
            ({payload.subCityFallback ? `none in ${subCityLabel(subCity)} yet, showing all of Addis` : subCityLabel(subCity)})
          </span>
        </legend>
        <AgentOption
          id={ANY_AGENT}
          selected={agentId === ANY_AGENT}
          onSelect={setAgentId}
          title="Any available agent"
          subtitle="Our staff assign the best available verified agent."
        />
        {agents.map((a) => (
          <AgentOption
            key={a.id}
            id={a.id}
            selected={agentId === a.id}
            onSelect={setAgentId}
            title={a.display_name}
            subtitle={`${TYPE_META[a.provider_type].label} · ${a.experience_years} yr experience${
              a.completed_count ? ` · ${a.completed_count} completed` : ""
            }${a.headline ? ` · ${a.headline}` : ""}`}
            avatar={<ProviderAvatar name={a.display_name} photoUrl={a.photo_url} entity={a.entity_type} verified={verifiedLevel(a)} />}
            extra={
              <span className="flex flex-wrap items-center gap-2">
                <ScoreBadge score={a.trust_score} isNew={a.rating_count < 3} />
                <RatingSummary value={a.rating_avg} count={a.rating_count} />
                <VerificationBadges provider={a} />
                <Link href={`/providers/${a.slug}`} target="_blank" className="text-primary text-xs underline">Profile</Link>
              </span>
            }
          />
        ))}
        {agents.length === 0 && (
          <p className="text-muted-foreground text-xs">No verified agents for this service yet. Staff will find one.</p>
        )}
      </fieldset>

      {!user ? (
        <div className="border-border bg-card rounded-md border p-5 text-sm">
          <p>Sign in to send your request. You can track it and review the agent afterwards.</p>
          <div className="mt-3 flex flex-wrap gap-3">
            <Link href={`/login?returnTo=${encodeURIComponent(returnTo)}`}>
              <Button>Sign in</Button>
            </Link>
            <Link href={`/register?returnTo=${encodeURIComponent(returnTo)}`}>
              <Button variant="outline">Create a free account</Button>
            </Link>
          </div>
        </div>
      ) : (
        <div className="border-border bg-card space-y-4 rounded-md border p-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Your name" htmlFor="pc-name" required error={errors.name}>
              <Input id="pc-name" value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Phone the agent should call" htmlFor="pc-phone" required error={errors.phone}>
              <Input id="pc-phone" type="tel" placeholder="09XXXXXXXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </Field>
          </div>
          <Field label="Details for the agent" htmlFor="pc-details">
            <Textarea id="pc-details" rows={3} value={details} onChange={(e) => setDetails(e.target.value)} />
          </Field>
          {submitError && <p className="text-destructive text-sm">{submitError}</p>}
          <Button size="lg" className="h-11 w-full text-base sm:w-auto" loading={isCreating} onClick={submit}>
            Send request to {agentId === ANY_AGENT ? "our staff" : agents.find((a) => a.id === agentId)?.display_name}
          </Button>
        </div>
      )}
    </div>
  );
}

function AgentOption({
  id,
  selected,
  onSelect,
  title,
  subtitle,
  avatar,
  extra,
}: {
  id: string;
  selected: boolean;
  onSelect: (id: string) => void;
  title: string;
  subtitle: string;
  avatar?: React.ReactNode;
  extra?: React.ReactNode;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center gap-3 rounded-md border p-3",
        selected ? "border-primary bg-secondary/50" : "border-border bg-card hover:border-primary/40",
      )}
    >
      <input
        type="radio"
        name="pc-agent"
        className="accent-primary size-4 shrink-0"
        checked={selected}
        onChange={() => onSelect(id)}
      />
      {avatar}
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{title}</span>
        <span className="text-muted-foreground block truncate text-xs">{subtitle}</span>
        {extra && <span className="mt-1 block">{extra}</span>}
      </span>
    </label>
  );
}
