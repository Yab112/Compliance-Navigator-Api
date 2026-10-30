"use client";

import { useId, useState } from "react";
import { Button } from "@cn/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@cn/ui/card";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { useCustomDataSource, useRunDataSource, useSaveCustomDataSource } from "@cn/core/api/admin";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { NativeSelect } from "@/modules/shared/native-select";
import { ErrorState, LoadingState } from "@/modules/shared/states";
import type { CustomDataSource, CustomDataSourceInput } from "@cn/core/types/admin";

const MAX_TEXT = 200_000;

const EMPTY: CustomDataSourceInput = {
  name: "",
  description: "",
  kind: "web_page",
  url: "",
  text: "",
  issuing_body: "",
  language: "en",
  tags: [],
  schedule: "manual",
  enabled: true,
};

function fromSource(s: CustomDataSource): CustomDataSourceInput {
  return {
    name: s.name,
    description: s.description,
    kind: s.kind,
    url: s.url ?? "",
    text: s.text ?? "",
    issuing_body: s.issuing_body ?? "",
    language: s.language,
    tags: s.tags,
    schedule: s.schedule,
    enabled: s.enabled,
  };
}

function Row({
  label,
  help,
  htmlFor,
  children,
  className,
}: {
  label: string;
  help?: React.ReactNode;
  htmlFor?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const helpId = htmlFor ? `${htmlFor}-help` : undefined;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      <label htmlFor={htmlFor} className="text-xs font-medium">
        {label}
      </label>
      {children}
      {help && (
        <p id={helpId} className="text-muted-foreground text-[11px] leading-snug">
          {help}
        </p>
      )}
    </div>
  );
}

/** Add or edit form. With `editId`, loads the source (including its pasted text) first. */
export function SourceForm({ editId, onDone }: { editId: string | null; onDone: (savedKey?: string) => void }) {
  const existing = useCustomDataSource(editId);
  if (editId && existing.isLoading) return <LoadingState />;
  if (editId && existing.error) {
    return <ErrorState error={existing.error} message={getErrorMessage(existing.error)} onRetry={() => existing.refetch()} />;
  }
  const initial = editId && existing.payload ? fromSource(existing.payload.source) : EMPTY;
  return <SourceFormBody key={editId ?? "new"} editId={editId} initial={initial} onDone={onDone} />;
}

function SourceFormBody({
  editId,
  initial,
  onDone,
}: {
  editId: string | null;
  initial: CustomDataSourceInput;
  onDone: (savedKey?: string) => void;
}) {
  const id = useId();
  const [form, setForm] = useState(initial);
  const [tagText, setTagText] = useState(initial.tags.join(", "));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "run" | null>(null);
  const { save } = useSaveCustomDataSource();
  const { runSource } = useRunDataSource();
  const set = <K extends keyof CustomDataSourceInput>(key: K, value: CustomDataSourceInput[K]) =>
    setForm((f) => ({ ...f, [key]: value }));
  const isPage = form.kind === "web_page";
  const textLength = (form.text ?? "").length;

  const submit = async (andRun: boolean) => {
    setBusy(andRun ? "run" : "save");
    setError(null);
    const body: CustomDataSourceInput = {
      ...form,
      url: form.url?.trim() || null,
      text: isPage ? null : form.text,
      issuing_body: form.issuing_body?.trim() || null,
      tags: tagText
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      schedule: isPage ? form.schedule : "manual",
    };
    try {
      const res = await save(editId, body);
      const key = res?.key ?? (editId ? `custom:${editId}` : undefined);
      if (andRun && key) await runSource(key);
      onDone(key);
    } catch (e) {
      setError(getErrorMessage(e, "Couldn't save the data source"));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card size="sm" className="mb-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(false);
        }}
      >
        <CardHeader>
          <CardTitle>{editId ? "Edit data source" : "Add a data source"}</CardTitle>
          <CardDescription>
            Add an official page or document so the AI assistant can answer from it and cite it. Each run reads the
            page (or your pasted text) again and replaces what the knowledge base had for this source.
          </CardDescription>
        </CardHeader>
        <CardContent className="mt-3 grid gap-4 sm:grid-cols-2">
          <Row label="Name" htmlFor={`${id}-name`} help="A short name staff will recognise, e.g. “Trade licence renewal directive”.">
            <Input
              id={`${id}-name`}
              required
              minLength={3}
              maxLength={120}
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </Row>
          <Row
            label="Issued by"
            htmlFor={`${id}-body`}
            help="The office that published it. Shown to citizens next to quotes from it."
          >
            <Input
              id={`${id}-body`}
              maxLength={200}
              placeholder="e.g. Ministry of Trade and Regional Integration"
              value={form.issuing_body ?? ""}
              onChange={(e) => set("issuing_body", e.target.value)}
            />
          </Row>
          <Row
            label="What it is and why it matters"
            htmlFor={`${id}-desc`}
            className="sm:col-span-2"
            help="Shown on the source card so the rest of the team knows why it was added."
          >
            <Textarea
              id={`${id}-desc`}
              maxLength={1000}
              rows={2}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
            />
          </Row>

          <fieldset className="flex min-w-0 flex-col gap-1 sm:col-span-2">
            <legend className="mb-1 text-xs font-medium">Where the text comes from</legend>
            <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
              {(
                [
                  ["web_page", "A web page or PDF", "We download it on every run, so updates on the site are picked up."],
                  ["pasted_text", "Text I paste here", "For documents that aren't online, or are only a scan."],
                ] as const
              ).map(([value, label, help]) => (
                <label key={value} className="flex max-w-xs items-start gap-2">
                  <input
                    type="radio"
                    name={`${id}-kind`}
                    value={value}
                    checked={form.kind === value}
                    onChange={() => set("kind", value)}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="font-medium">{label}</span>
                    <span className="text-muted-foreground block text-[11px]">{help}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <Row
            label={isPage ? "Page address (URL)" : "Link to the original (optional)"}
            htmlFor={`${id}-url`}
            className="sm:col-span-2"
            help={
              isPage
                ? "A public http:// or https:// address of the official page or PDF (up to 2 MB). Pages that need a login, and addresses inside our own network, can't be read."
                : "Where citizens can see the original. Shown as the source of quotes."
            }
          >
            <Input
              id={`${id}-url`}
              type="url"
              inputMode="url"
              required={isPage}
              maxLength={2000}
              placeholder="https://"
              value={form.url ?? ""}
              onChange={(e) => set("url", e.target.value)}
            />
          </Row>

          {!isPage && (
            <Row
              label="Document text"
              htmlFor={`${id}-text`}
              className="sm:col-span-2"
              help={`${textLength.toLocaleString("en")} of ${MAX_TEXT.toLocaleString("en")} characters. Paste the full text; it is split into short passages for the assistant.`}
            >
              <Textarea
                id={`${id}-text`}
                required
                minLength={50}
                maxLength={MAX_TEXT}
                rows={8}
                value={form.text ?? ""}
                onChange={(e) => set("text", e.target.value)}
              />
            </Row>
          )}

          <Row label="Language" htmlFor={`${id}-lang`}>
            <NativeSelect
              id={`${id}-lang`}
              value={form.language}
              onChange={(e) => set("language", e.target.value as "en" | "am")}
            >
              <option value="en">English</option>
              <option value="am">Amharic</option>
            </NativeSelect>
          </Row>
          <Row
            label="Topics"
            htmlFor={`${id}-tags`}
            help="Up to 10 words separated by commas, e.g. trade licence, renewal, tax."
          >
            <Input
              id={`${id}-tags`}
              value={tagText}
              onChange={(e) => setTagText(e.target.value)}
              placeholder="trade licence, renewal"
            />
          </Row>
          <Row
            label="When it runs"
            htmlFor={`${id}-schedule`}
            help={
              isPage
                ? "Daily and weekly runs need the background worker to be running on the server."
                : "Pasted text only changes when you edit it, so it runs when you press Run now."
            }
          >
            <NativeSelect
              id={`${id}-schedule`}
              value={isPage ? form.schedule : "manual"}
              disabled={!isPage}
              onChange={(e) => set("schedule", e.target.value as CustomDataSourceInput["schedule"])}
            >
              <option value="manual">Only when someone presses Run now</option>
              <option value="daily">Every day</option>
              <option value="weekly">Every week</option>
            </NativeSelect>
          </Row>
          <div className="flex items-start gap-2 self-end text-xs">
            <input
              id={`${id}-enabled`}
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => set("enabled", e.target.checked)}
              className="mt-0.5"
            />
            <label htmlFor={`${id}-enabled`}>
              <span className="font-medium">Turned on</span>
              <span className="text-muted-foreground block text-[11px]">
                Untick to save it paused: it won&apos;t run until someone resumes it.
              </span>
            </label>
          </div>
        </CardContent>
        <CardFooter className="mt-3 flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-end">
          {error && (
            <p role="alert" className="text-destructive text-[11px] sm:mr-auto">
              {error}
            </p>
          )}
          <Button type="button" variant="outline" size="sm" disabled={!!busy} onClick={() => onDone()}>
            Cancel
          </Button>
          <Button type="submit" variant="outline" size="sm" loading={busy === "save"} disabled={!!busy}>
            {editId ? "Save changes" : "Save"}
          </Button>
          <Button
            type="button"
            size="sm"
            loading={busy === "run"}
            disabled={!!busy || !form.enabled}
            title={!form.enabled ? "Turn the source on to run it" : undefined}
            onClick={(e) => {
              const formEl = e.currentTarget.form;
              if (formEl && !formEl.reportValidity()) return;
              submit(true);
            }}
          >
            Save and run now
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
