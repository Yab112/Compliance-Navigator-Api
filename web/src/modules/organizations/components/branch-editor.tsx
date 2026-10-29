"use client";

import { useState } from "react";
import { useOrgAction } from "@/api/organizations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiPaths } from "@/lib/constants/api-paths";
import { MTD } from "@/lib/constants/methods";
import { getErrorMessage } from "@/lib/errors";
import { Field, NativeSelect, SubCityOptions } from "@/modules/guday/components/shared";
import type { Branch, BranchInput, HoursDay, Weekday } from "@/types/organizations";

const DAYS: { day: Weekday; label: string; am: string }[] = [
  { day: "mon", label: "Monday", am: "ሰኞ" },
  { day: "tue", label: "Tuesday", am: "ማክሰኞ" },
  { day: "wed", label: "Wednesday", am: "ረቡዕ" },
  { day: "thu", label: "Thursday", am: "ሐሙስ" },
  { day: "fri", label: "Friday", am: "ዓርብ" },
  { day: "sat", label: "Saturday", am: "ቅዳሜ" },
  { day: "sun", label: "Sunday", am: "እሑድ" },
];

const WEEKDAY: Omit<HoursDay, "day"> = { closed: false, open: "08:30", close: "17:30", lunch_start: "12:30", lunch_end: "13:30" };
const CLOSED: Omit<HoursDay, "day"> = { closed: true, open: null, close: null, lunch_start: null, lunch_end: null };

/** The usual government week: Monday to Friday with the lunch break, optional Saturday morning. */
export function standardWeek(saturday: boolean): HoursDay[] {
  return DAYS.map(({ day }) =>
    day === "sun"
      ? { day, ...CLOSED }
      : day === "sat"
        ? saturday
          ? { day, closed: false, open: "08:30", close: "12:30", lunch_start: null, lunch_end: null }
          : { day, ...CLOSED }
        : { day, ...WEEKDAY },
  );
}

export const EMPTY_BRANCH: BranchInput = {
  name: "",
  region: "Addis Ababa",
  sub_city: "",
  woreda: "",
  address: "",
  landmark: "",
  phone: "",
  email: "",
  map_url: "",
  hours: "",
  hours_schedule: standardWeek(false),
};

/** Week grid: open and close times, lunch break, closed days. */
export function HoursGrid({ value, onChange }: { value: HoursDay[]; onChange: (v: HoursDay[]) => void }) {
  const rows = DAYS.map(({ day }) => value.find((d) => d.day === day) ?? { day, ...CLOSED });
  const update = (day: Weekday, patch: Partial<HoursDay>) =>
    onChange(rows.map((r) => (r.day === day ? { ...r, ...patch } : r)));
  const time = (d: HoursDay, key: "open" | "close" | "lunch_start" | "lunch_end", label: string) => (
    <Input
      type="time"
      aria-label={`${label} ${d.day}`}
      className="h-8 w-[6.5rem]"
      value={d[key] ?? ""}
      disabled={d.closed}
      onChange={(e) => update(d.day, { [key]: e.target.value || null })}
    />
  );
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" onClick={() => onChange(standardWeek(false))}>
          Mon to Fri, lunch 12:30
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => onChange(standardWeek(true))}>
          Plus Saturday morning
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="text-sm">
          <thead className="text-muted-foreground text-xs">
            <tr>
              <th className="py-1 pr-3 text-left font-medium">Day</th>
              <th className="py-1 pr-3 text-left font-medium">Open</th>
              <th className="py-1 pr-2 text-left font-medium">Opens</th>
              <th className="py-1 pr-3 text-left font-medium">Closes</th>
              <th className="py-1 pr-2 text-left font-medium">Lunch from</th>
              <th className="py-1 text-left font-medium">to</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => {
              const meta = DAYS.find((x) => x.day === d.day)!;
              return (
                <tr key={d.day}>
                  <td className="py-1 pr-3 whitespace-nowrap">
                    {meta.label} <span className="text-muted-foreground text-xs">{meta.am}</span>
                  </td>
                  <td className="py-1 pr-3">
                    <input
                      type="checkbox"
                      aria-label={`Open on ${meta.label}`}
                      checked={!d.closed}
                      onChange={(e) =>
                        update(d.day, e.target.checked ? { ...WEEKDAY, lunch_start: d.day === "sat" ? null : "12:30", lunch_end: d.day === "sat" ? null : "13:30" } : CLOSED)
                      }
                    />
                  </td>
                  <td className="py-1 pr-2">{time(d, "open", "Opens")}</td>
                  <td className="py-1 pr-3">{time(d, "close", "Closes")}</td>
                  <td className="py-1 pr-2">{time(d, "lunch_start", "Lunch from")}</td>
                  <td className="py-1">{time(d, "lunch_end", "Lunch to")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Add or edit one branch, saved straight to the organization. */
export function BranchForm({
  orgId,
  branch,
  onDone,
}: {
  orgId: string;
  branch: Branch | null;
  onDone: () => void;
}) {
  const action = useOrgAction();
  const [data, setData] = useState<BranchInput>(() =>
    branch
      ? { ...EMPTY_BRANCH, ...branch, hours_schedule: branch.hours_schedule?.length ? branch.hours_schedule : standardWeek(false) }
      : { ...EMPTY_BRANCH },
  );
  const [err, setErr] = useState<string | null>(null);
  const set = (patch: Partial<BranchInput>) => setData((d) => ({ ...d, ...patch }));
  const text = (k: "name" | "woreda" | "address" | "landmark" | "phone" | "email" | "map_url" | "region", label: string, hint?: string) => (
    <Field label={label} htmlFor={`br-${k}`} required={k === "name"} hint={hint}>
      <Input id={`br-${k}`} value={(data[k] as string | null | undefined) ?? ""} onChange={(e) => set({ [k]: e.target.value })} required={k === "name"} />
    </Field>
  );

  const save = async () => {
    setErr(null);
    const body = Object.fromEntries(
      Object.entries({ ...data, hours: null }).map(([k, v]) => [k, typeof v === "string" ? v.trim() || null : v]),
    );
    try {
      await action.mutateAsync({
        url: branch ? apiPaths.org.branch(orgId, branch.id) : apiPaths.org.branches(orgId),
        method: branch ? MTD.PUT : MTD.POST,
        body,
      });
      onDone();
    } catch (e) {
      setErr(getErrorMessage(e));
    }
  };

  return (
    <form
      className="bg-secondary/40 space-y-4 rounded-md p-4"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {text("name", "Branch name · የቅርንጫፍ ስም", "As people know it, e.g. Bole branch")}
        {text("region", "Region or city")}
        <Field label="Sub-city" htmlFor="br-sub_city">
          <NativeSelect id="br-sub_city" className="h-9" value={data.sub_city ?? ""} onChange={(e) => set({ sub_city: e.target.value })}>
            <SubCityOptions placeholder="Outside Addis Ababa / not set" />
          </NativeSelect>
        </Field>
        {text("woreda", "Woreda")}
        {text("address", "Address · አድራሻ", "Street, building and floor")}
        {text("landmark", "Landmark", "What people can see nearby")}
        {text("phone", "Phone")}
        {text("email", "Email")}
        {text("map_url", "Map link", "Google Maps link to the entrance")}
      </div>
      <div>
        <p className="mb-2 text-xs font-medium">Opening hours · የሥራ ሰዓት</p>
        <HoursGrid value={data.hours_schedule ?? []} onChange={(v) => set({ hours_schedule: v })} />
      </div>
      {err && <p className="text-destructive text-sm">{err}</p>}
      <div className="flex gap-2">
        <Button type="submit" loading={action.isPending}>
          Save branch
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** List of branches with add, edit and remove. */
export function BranchesManager({ orgId, branches }: { orgId: string; branches: Branch[] }) {
  const action = useOrgAction();
  const [editing, setEditing] = useState<Branch | "new" | null>(null);
  return (
    <div className="space-y-4">
      {editing && <BranchForm orgId={orgId} branch={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}
      {branches.length === 0 && !editing && <p className="text-muted-foreground text-sm">No branches yet.</p>}
      <ul className="divide-border divide-y">
        {branches.map((b) => (
          <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
            <div>
              <p className="font-medium">{b.name}</p>
              <p className="text-muted-foreground text-xs">
                {[b.address, b.woreda && `Woreda ${b.woreda}`, b.sub_city, b.phone].filter(Boolean).join(" · ")}
              </p>
              <p className="text-xs">{b.hours || "Hours not set"}</p>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setEditing(b)}>
                Edit
              </Button>
              <Button size="sm" variant="outline" onClick={() => action.mutate({ url: apiPaths.org.branch(orgId, b.id), method: MTD.DELETE })}>
                Remove
              </Button>
            </div>
          </li>
        ))}
      </ul>
      {!editing && (
        <Button type="button" variant="outline" onClick={() => setEditing("new")}>
          + Add a branch
        </Button>
      )}
    </div>
  );
}
