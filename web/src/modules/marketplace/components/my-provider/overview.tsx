"use client";

import { useRemoveProviderPhoto, useUploadProviderFile } from "@cn/core/api/providers";
import type { MyProvider } from "@cn/core/types/provider";
import { PhotoUploader } from "@/modules/marketplace/components/photo-uploader";
import { verifiedLevel } from "@cn/ui/marketplace/provider-avatar";
import { ScoreBreakdown } from "@cn/ui/marketplace/trust";
import { PayoutCard } from "@/modules/marketplace/components/payout-card";
import { Card, CompletenessRing } from "@/modules/marketplace/components/my-provider/shared";

export function Overview({ p }: { p: MyProvider }) {
  const upload = useUploadProviderFile();
  const removePhoto = useRemoveProviderPhoto();
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title={p.entity_type === "company" ? "Company logo" : "Profile photo"} className="lg:col-span-2">
        <PhotoUploader
          name={p.display_name}
          entity={p.entity_type}
          verified={p.status === "approved" ? verifiedLevel(p) : null}
          currentUrl={p.photo_url}
          onSave={(file) => upload("photo", file)}
          onRemove={p.photo_url ? () => removePhoto() : undefined}
        />
      </Card>
      <PayoutCard className="lg:col-span-2" />
      <Card title="Profile completeness">
        <div className="flex items-center gap-4">
          <CompletenessRing percent={p.completeness.percent} />
          <p className="text-muted-foreground text-xs leading-relaxed">
            Complete profiles appear higher and get more requests. Finish the open items below.
          </p>
        </div>
        <ul className="mt-4 grid gap-1.5 text-xs sm:grid-cols-2">
          {p.completeness.items.map((i) => (
            <li key={i.key} className={i.done ? "text-primary" : "text-muted-foreground"}>
              {i.done ? "✓" : "○"} {i.label}
            </li>
          ))}
        </ul>
      </Card>
      <Card title={`Trust score ${p.trust_score}/100`}>
        <ScoreBreakdown parts={p.score_breakdown} />
        {p.tips.length > 0 && (
          <div className="bg-secondary/50 mt-4 rounded-lg p-3 text-xs">
            <p className="font-semibold">How to raise it</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {p.tips.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}
