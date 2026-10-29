"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { SETTINGS_HISTORY_PAGE_SIZE, usePlatformSettings, useSaveSettings, useSettingsHistory } from "@cn/core/api/admin/settings";
import { getErrorMessage } from "@cn/core/lib/errors";
import { formatDateTime } from "@cn/core/lib/format";
import { cn } from "@cn/core/lib/utils";
import type { SettingField, SettingGroup, SettingValue } from "@cn/core/types/settings";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage, useUrlPageSize } from "@cn/ui/pager";
import { AdminPage } from "@/modules/components/admin-page";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";

const HISTORY = "history";

/** "15 %", "100 ETB", "On"; how a value reads in hints and the change history. */
function show(value: SettingValue | null | undefined, field?: Pick<SettingField, "type" | "unit"> | null): string {
  if (value === null || value === undefined || value === "") return "empty";
  if (typeof value === "boolean") return value ? "On" : "Off";
  if (typeof value === "number") return `${value.toLocaleString("en-US")}${field?.unit ? ` ${field.unit}` : ""}`;
  return value;
}

/** Same rules the server applies, so mistakes show before saving. */
function problem(field: SettingField, raw: string | boolean): string | null {
  if (field.type === "bool") return null;
  const text = String(raw).trim();
  if (field.type === "text") {
    if (field.required && !text) return "Required";
    if (text && field.pattern && !new RegExp(field.pattern).test(text)) return `Must be ${field.pattern_hint}`;
    return null;
  }
  if (!text) return "Required";
  const n = Number(text);
  if (Number.isNaN(n)) return "Enter a number";
  if (field.type === "int" && !Number.isInteger(n)) return "Whole numbers only";
  if ((field.min !== null && n < field.min) || (field.max !== null && n > field.max)) {
    return `Between ${field.min} and ${field.max}${field.unit ? ` ${field.unit}` : ""}`;
  }
  return null;
}

function toValue(field: SettingField, raw: string | boolean): SettingValue {
  if (field.type === "bool") return raw as boolean;
  if (field.type === "text") return String(raw).trim();
  return Number(raw);
}

function FieldInput({ field, raw, onChange, error }: { field: SettingField; raw: string | boolean; onChange: (v: string | boolean) => void; error: string | null }) {
  const id = `setting-${field.key}`;
  if (field.type === "bool") {
    return (
      <label htmlFor={id} className="flex items-center gap-2 text-sm">
        <input id={id} type="checkbox" className="accent-primary size-4" checked={raw as boolean} onChange={(e) => onChange(e.target.checked)} />
        {raw ? "On" : "Off"}
      </label>
    );
  }
  const numeric = field.type !== "text";
  return (
    <div className="flex max-w-xs items-center gap-2">
      <Input
        id={id}
        type={numeric ? "number" : "text"}
        inputMode={numeric ? "decimal" : undefined}
        step={field.type === "int" ? 1 : numeric ? 0.01 : undefined}
        min={field.min ?? undefined}
        max={field.max ?? undefined}
        value={raw as string}
        placeholder={field.placeholder ?? undefined}
        aria-invalid={!!error}
        aria-describedby={`${id}-help`}
        onChange={(e) => onChange(e.target.value)}
      />
      {field.unit && <span className="text-muted-foreground shrink-0 text-xs">{field.unit}</span>}
    </div>
  );
}

/** One group's form. Every change in the group is saved together; the server checks all of it first. */
type Notice = { ok: boolean; text: string } | null;

function GroupForm({ group, notice, onNotice }: { group: SettingGroup; notice: Notice; onNotice: (n: Notice) => void }) {
  const initial = useMemo(
    () => Object.fromEntries(group.fields.map((f) => [f.key, f.type === "bool" ? (f.value as boolean) : String(f.value ?? "")])),
    [group],
  );
  const [draft, setDraft] = useState<Record<string, string | boolean>>(initial);
  const { save, reset, isPending } = useSaveSettings();

  const errors = Object.fromEntries(group.fields.map((f) => [f.key, problem(f, draft[f.key])]));
  const changed = group.fields.filter((f) => !problem(f, draft[f.key]) && toValue(f, draft[f.key]) !== f.value);
  const invalid = group.fields.some((f) => errors[f.key] && draft[f.key] !== initial[f.key]);
  const dirty = group.fields.some((f) => draft[f.key] !== initial[f.key]);

  const submit = async () => {
    onNotice(null);
    try {
      const res = await save(Object.fromEntries(changed.map((f) => [f.key, toValue(f, draft[f.key])])));
      // Money and tax changes wait for a second staff member (Access, Approvals)
      if ("approval" in res) {
        onNotice({ ok: true, text: "Money and tax changes need a second person: sent to Approvals. Nothing changes until someone else approves it." });
        return;
      }
      const names = group.fields.filter((f) => res.changed?.includes(f.key)).map((f) => f.label);
      onNotice({ ok: true, text: names.length ? `Saved: ${names.join(", ")}.` : "Nothing changed." });
    } catch (err) {
      onNotice({ ok: false, text: getErrorMessage(err, "Could not save") });
    }
  };

  return (
    <form
      className="space-y-1"
      onSubmit={(e) => {
        e.preventDefault();
        if (changed.length && !invalid) void submit();
      }}
    >
      <ul className="divide-border divide-y">
        {group.fields.map((f) => {
          const fieldDirty = draft[f.key] !== initial[f.key];
          return (
            <li key={f.key} className="grid gap-2 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] md:gap-6">
              <div>
                <label htmlFor={`setting-${f.key}`} className="text-sm font-medium">
                  {f.label}
                  {f.required && <span className="text-destructive"> *</span>}
                </label>
                <p id={`setting-${f.key}-help`} className="text-muted-foreground mt-0.5 text-xs">{f.help}</p>
                {f.applies && <p className="text-muted-foreground mt-1 text-[11px]">Applies to: {f.applies}</p>}
              </div>
              <div className="space-y-1">
                <FieldInput field={f} raw={draft[f.key]} error={errors[f.key]} onChange={(v) => setDraft((d) => ({ ...d, [f.key]: v }))} />
                {errors[f.key] && fieldDirty && <p className="text-destructive text-[11px]">{errors[f.key]}</p>}
                <p className="text-muted-foreground text-[11px]">
                  {f.is_default ? (
                    <>Default value</>
                  ) : (
                    <>
                      Changed{f.updated_by ? ` by ${f.updated_by}` : ""} {formatDateTime(f.updated_at)} · default {show(f.default, f)}{" "}
                      <button
                        type="button"
                        className="text-primary hover:underline"
                        disabled={isPending}
                        onClick={async () => {
                          onNotice(null);
                          try {
                            const res = await reset(f.key);
                            onNotice({
                              ok: true,
                              text: "approval" in res
                                ? `Resetting ${f.label} needs a second person: sent to Approvals.`
                                : `${f.label} is back to its default.`,
                            });
                          } catch (err) {
                            onNotice({ ok: false, text: getErrorMessage(err, "Could not reset") });
                          }
                        }}
                      >
                        Reset to default
                      </button>
                    </>
                  )}
                  {fieldDirty && !errors[f.key] && <span className="text-gov-ink font-medium"> · was {show(f.value, f)}</span>}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="bg-card sticky bottom-0 flex flex-wrap items-center gap-3 border-t py-3">
        <Button type="submit" disabled={!changed.length || invalid} loading={isPending}>
          {changed.length ? `Save ${changed.length} change${changed.length > 1 ? "s" : ""}` : "Save"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={!dirty || isPending}
          onClick={() => {
            setDraft(initial);
            onNotice(null);
          }}
        >
          Discard
        </Button>
        {notice && (
          <p className={notice.ok ? "text-primary text-sm" : "text-destructive text-sm"} role={notice.ok ? "status" : "alert"}>
            {notice.text}
          </p>
        )}
      </div>
    </form>
  );
}

function History() {
  const [page, setPage] = useUrlPage();
  const [size, setSize] = useUrlPageSize(SETTINGS_HISTORY_PAGE_SIZE);
  const { payload, isLoading, isError, error, refetch } = useSettingsHistory(page, size);
  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={error?.message ?? "Could not load the history"} onRetry={() => refetch()} />;
  if (!payload?.items.length) return <EmptyState title="No settings have been changed yet." />;
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="text-muted-foreground text-xs">
            <tr>
              <th scope="col" className="py-2 font-medium">When</th>
              <th scope="col" className="py-2 font-medium">Setting</th>
              <th scope="col" className="py-2 font-medium">Change</th>
              <th scope="col" className="py-2 font-medium">By</th>
            </tr>
          </thead>
          <tbody className="divide-border divide-y">
            {payload.items.map((h) => (
              <tr key={h.id}>
                <td className="py-2 whitespace-nowrap">{formatDateTime(h.changed_at)}</td>
                <td className="py-2">{h.label}</td>
                <td className="py-2">
                  <span className="text-muted-foreground">{show(h.old_value, { type: "text", unit: h.unit })}</span> →{" "}
                  <span className="font-medium">{show(h.new_value, { type: "text", unit: h.unit })}</span>
                </td>
                <td className="py-2">{h.changed_by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager className="mt-4" page={page} pageSize={size} total={payload.total} onPage={setPage} onPageSize={setSize} />
    </>
  );
}

export function SettingsPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { payload, isLoading, isError, error, refetch } = usePlatformSettings();
  // Lives here: a save re-keys the form below, which would drop a message kept inside it
  const [notice, setNotice] = useState<Notice>(null);
  const groups = payload?.groups ?? [];
  const tab = params.get("group") ?? groups[0]?.key ?? "";
  const active = groups.find((g) => g.key === tab);
  const tabs = [...groups.map((g) => ({ key: g.key, label: g.title, count: g.fields.filter((f) => !f.is_default).length })), { key: HISTORY, label: "Change history", count: 0 }];

  const open = (key: string) => {
    setNotice(null);
    const sp = new URLSearchParams();
    if (key !== groups[0]?.key) sp.set("group", key);
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) return;
    e.preventDefault();
    const i = tabs.findIndex((t) => t.key === tab);
    const next = tabs[(i + (e.key === "ArrowUp" || e.key === "ArrowLeft" ? tabs.length - 1 : 1)) % tabs.length];
    open(next.key);
    document.getElementById(`settings-tab-${next.key}`)?.focus();
  };

  return (
    <AdminPage
      title="Platform settings · የመድረክ ቅንብሮች"
      description="Business rules the platform runs on. Changes take effect within seconds and every change is recorded. Payment keys and other secrets stay in the server configuration."
    >
      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={error?.message ?? "Could not load settings"} onRetry={() => refetch()} />
      ) : (
        <div className="flex flex-col gap-6 md:flex-row">
          <div role="tablist" aria-label="Settings" aria-orientation="vertical" className="flex gap-1 overflow-x-auto md:w-56 md:shrink-0 md:flex-col">
            {tabs.map((t) => (
              <button
                key={t.key}
                id={`settings-tab-${t.key}`}
                type="button"
                role="tab"
                aria-selected={t.key === tab}
                aria-controls="settings-panel"
                tabIndex={t.key === tab ? 0 : -1}
                onClick={() => open(t.key)}
                onKeyDown={onKeyDown}
                className={cn(
                  "flex shrink-0 items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm",
                  t.key === tab ? "bg-secondary text-gov-ink font-medium" : "text-muted-foreground hover:bg-secondary/50",
                )}
              >
                {t.label}
                {t.count > 0 && <span className="text-muted-foreground text-[11px]" title="Changed from default">{t.count} changed</span>}
              </button>
            ))}
          </div>
          <section role="tabpanel" id="settings-panel" aria-labelledby={`settings-tab-${tab}`} className="border-border bg-card min-w-0 flex-1 rounded-md border px-5 pt-4">
            {active ? (
              <>
                <h2 className="font-semibold">
                  {active.title} <span className="text-muted-foreground text-sm font-normal">· {active.am}</span>
                </h2>
                <p className="text-muted-foreground mt-1 text-xs">{active.description}</p>
                {/* Keyed by the saved values so the form resets after a save or reset */}
                <GroupForm key={JSON.stringify(active.fields.map((f) => [f.key, f.value]))} group={active} notice={notice} onNotice={setNotice} />
              </>
            ) : (
              <div className="pb-5">
                <h2 className="mb-3 font-semibold">Change history</h2>
                <History />
              </div>
            )}
          </section>
        </div>
      )}
    </AdminPage>
  );
}
