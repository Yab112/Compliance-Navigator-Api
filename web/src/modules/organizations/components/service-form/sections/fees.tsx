"use client";

import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Field, NativeSelect } from "@cn/ui/guday/shared";
import { FEE_CATEGORY_LABEL, type FeeCategory, type FeeRow } from "@cn/core/types/organizations";
import { num, type SectionProps } from "@/modules/organizations/components/service-form/model";

const EMPTY_FEE: FeeRow = { category: "everyone", speed: "regular", amount_min: 0, amount_max: null, currency: "ETB", covers: "", notes: "" };

export function FeesSection({ form, set }: SectionProps) {
  const update = (i: number, patch: Partial<FeeRow>) => set({ fee_schedule: form.fee_schedule.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  return (
    <div className="space-y-5">
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.is_free} onChange={(e) => set({ is_free: e.target.checked, fee_schedule: e.target.checked ? [] : form.fee_schedule })} />
        This service is free
      </label>
      {!form.is_free && (
        <div className="space-y-3">
          <p className="text-muted-foreground text-sm">
            One line per price. Different prices for foreign nationals, companies or urgent service go on their own line.
          </p>
          {form.fee_schedule.map((r, i) => (
            <div key={i} className="border-border grid gap-3 rounded-md border p-3 sm:grid-cols-[1fr_120px_110px_110px_90px_auto]">
              <Field label="Who pays this" htmlFor={`fee-cat-${i}`}>
                <NativeSelect id={`fee-cat-${i}`} className="h-9" value={r.category} onChange={(e) => update(i, { category: e.target.value as FeeCategory })}>
                  {(Object.entries(FEE_CATEGORY_LABEL) as [FeeCategory, string][]).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field label="Speed" htmlFor={`fee-speed-${i}`}>
                <NativeSelect id={`fee-speed-${i}`} className="h-9" value={r.speed} onChange={(e) => update(i, { speed: e.target.value as FeeRow["speed"] })}>
                  <option value="regular">Regular</option>
                  <option value="urgent">Urgent</option>
                </NativeSelect>
              </Field>
              <Field label="Amount" htmlFor={`fee-min-${i}`}>
                <Input id={`fee-min-${i}`} type="number" min={0} value={r.amount_min} onChange={(e) => update(i, { amount_min: Number(e.target.value || 0) })} />
              </Field>
              <Field label="Up to" htmlFor={`fee-max-${i}`} hint="If it varies">
                <Input id={`fee-max-${i}`} type="number" min={0} value={r.amount_max ?? ""} onChange={(e) => update(i, { amount_max: num(e.target.value) })} />
              </Field>
              <Field label="Currency" htmlFor={`fee-cur-${i}`}>
                <NativeSelect id={`fee-cur-${i}`} className="h-9" value={r.currency} onChange={(e) => update(i, { currency: e.target.value as FeeRow["currency"] })}>
                  <option value="ETB">ETB</option>
                  <option value="USD">USD</option>
                </NativeSelect>
              </Field>
              <div className="flex items-end">
                <Button type="button" variant="ghost" size="sm" aria-label="Remove fee line" onClick={() => set({ fee_schedule: form.fee_schedule.filter((_, j) => j !== i) })}>
                  ✕
                </Button>
              </div>
              <Field label="What it covers" htmlFor={`fee-covers-${i}`} className="sm:col-span-3">
                <Input id={`fee-covers-${i}`} value={r.covers ?? ""} onChange={(e) => update(i, { covers: e.target.value })} placeholder="e.g. Per copy" />
              </Field>
              <Field label="Notes" htmlFor={`fee-notes-${i}`} className="sm:col-span-3">
                <Input id={`fee-notes-${i}`} value={r.notes ?? ""} onChange={(e) => update(i, { notes: e.target.value })} placeholder="e.g. Plus 0.5% of the contract value" />
              </Field>
            </div>
          ))}
          <Button type="button" variant="outline" onClick={() => set({ fee_schedule: [...form.fee_schedule, { ...EMPTY_FEE }] })}>
            + Add a price line
          </Button>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Payment methods" htmlFor="f-pay" hint="Comma separated, e.g. Cash, Telebirr, CBE Birr">
          <Input id="f-pay" value={form.payment_methods.join(", ")} onChange={(e) => set({ payment_methods: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
        </Field>
        <Field label="Where to pay" htmlFor="f-where" hint="e.g. Cashier next to Window 1, or a CBE branch">
          <Input id="f-where" value={form.where_to_pay ?? ""} onChange={(e) => set({ where_to_pay: e.target.value })} />
        </Field>
        <Field label="Processing time, as people should read it" htmlFor="t-text" required>
          <Input id="t-text" value={form.processing_time_text ?? ""} onChange={(e) => set({ processing_time_text: e.target.value })} placeholder="Same day" />
        </Field>
        <Field label="Processing time in minutes" htmlFor="t-min" hint="Used to add up full paths across offices">
          <Input id="t-min" type="number" min={0} value={form.processing_minutes ?? ""} onChange={(e) => set({ processing_minutes: num(e.target.value) })} />
        </Field>
      </div>
    </div>
  );
}
