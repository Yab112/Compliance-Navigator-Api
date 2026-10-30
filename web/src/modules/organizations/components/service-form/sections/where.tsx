"use client";

import Link from "next/link";
import { Input } from "@cn/ui/input";
import { Field, NativeSelect } from "@cn/ui/guday/shared";
import {
  PROXY_LABEL,
  type Branch,
  type BranchDetail,
  type ProxyAllowed,
} from "@cn/core/types/organizations";
import type { SectionProps } from "@/modules/organizations/components/service-form/model";

export function WhereSection({ form, set, branches, orgId }: SectionProps & { branches: Branch[]; orgId: string }) {
  const detail = (id: string): BranchDetail => form.branch_details.find((d) => d.branch_id === id) ?? { branch_id: id };
  const setDetail = (id: string, patch: Partial<BranchDetail>) =>
    set({ branch_details: [...form.branch_details.filter((d) => d.branch_id !== id), { ...detail(id), ...patch }] });
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium">Branches that offer it</p>
        {branches.length === 0 ? (
          <p className="text-muted-foreground mt-1 text-sm">
            No branches yet. Add them in{" "}
            <Link href={`/org/${orgId}`} className="text-primary underline">
              the dashboard
            </Link>{" "}
            or the registration step for branches.
          </p>
        ) : (
          <ul className="mt-2 space-y-3">
            {branches.map((b) => {
              const on = form.branch_ids.includes(b.id);
              const d = detail(b.id);
              return (
                <li key={b.id} className="border-border rounded-md border p-3">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input type="checkbox" checked={on} onChange={(e) => set({ branch_ids: e.target.checked ? [...form.branch_ids, b.id] : form.branch_ids.filter((x) => x !== b.id) })} />
                    {b.name}
                    <span className="text-muted-foreground text-xs font-normal">{b.hours}</span>
                  </label>
                  {on && (
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <Field label="Window or desk" htmlFor={`bd-w-${b.id}`}>
                        <Input id={`bd-w-${b.id}`} value={d.window ?? ""} onChange={(e) => setDetail(b.id, { window: e.target.value })} placeholder="Window 2" />
                      </Field>
                      <Field label="Phone for this service" htmlFor={`bd-p-${b.id}`}>
                        <Input id={`bd-p-${b.id}`} value={d.phone ?? ""} onChange={(e) => setDetail(b.id, { phone: e.target.value })} />
                      </Field>
                      <Field label="Hours differ for this service?" htmlFor={`bd-h-${b.id}`} hint="e.g. Applications only in the morning">
                        <Input id={`bd-h-${b.id}`} value={d.hours_note ?? ""} onChange={(e) => setDetail(b.id, { hours_note: e.target.value })} />
                      </Field>
                      <Field label="Notes for this branch" htmlFor={`bd-n-${b.id}`}>
                        <Input id={`bd-n-${b.id}`} value={d.notes ?? ""} onChange={(e) => setDetail(b.id, { notes: e.target.value })} />
                      </Field>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={form.appointment_required} onChange={(e) => set({ appointment_required: e.target.checked })} />
          An appointment is needed before coming
        </label>
        {form.appointment_required && (
          <>
            <Field label="How to book" htmlFor="ap-how" className="sm:col-span-2">
              <Input id="ap-how" value={form.appointment_how ?? ""} onChange={(e) => set({ appointment_how: e.target.value })} placeholder="Call the desk a day before" />
            </Field>
            <Field label="Booking link" htmlFor="ap-url">
              <Input id="ap-url" type="url" value={form.appointment_url ?? ""} onChange={(e) => set({ appointment_url: e.target.value })} />
            </Field>
            <Field label="Booking phone" htmlFor="ap-phone">
              <Input id="ap-phone" value={form.appointment_phone ?? ""} onChange={(e) => set({ appointment_phone: e.target.value })} />
            </Field>
          </>
        )}
        <Field label="Can someone apply on the applicant's behalf?" htmlFor="proxy">
          <NativeSelect id="proxy" className="h-9" value={form.proxy_allowed ?? ""} onChange={(e) => set({ proxy_allowed: (e.target.value || null) as ProxyAllowed | null })}>
            <option value="">Choose</option>
            {(Object.entries(PROXY_LABEL) as [ProxyAllowed, string][]).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Notes on applying for someone" htmlFor="proxy-notes" hint="Agents on the platform read this before taking a job">
          <Input id="proxy-notes" value={form.proxy_notes ?? ""} onChange={(e) => set({ proxy_notes: e.target.value })} />
        </Field>
      </div>
    </div>
  );
}
