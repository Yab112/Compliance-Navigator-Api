import Image from "next/image";
import Link from "next/link";
import { ReportIssue } from "@/components/feedback/report-issue";
import { Badge } from "@cn/ui/badge";
import { Separator } from "@cn/ui/separator";
import type { RoadmapStep } from "@/types/roadmap";
import { getDocumentLabel } from "@/lib/mock-roadmap";
import { officeStockByStep, stockImages } from "@/content/stock-images";
import { OrgServiceBlock } from "@/components/roadmap/org-service-block";

function MesobBlock({ mesob }: { mesob: NonNullable<RoadmapStep["mesob"]> }) {
  return (
    <div className="border-primary/30 bg-primary/5 space-y-2 border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-semibold">Available at MESOB one-stop centers</h4>
        <Badge variant="outline">{mesob.institution}</Badge>
      </div>
      <p className="font-medium">{mesob.serviceName}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <p>
          <strong>Fee:</strong> {mesob.feeText ?? "Confirm at the center"}
        </p>
        <p>
          <strong>Processing:</strong> {mesob.processingTimeText ?? "Not published"}
        </p>
      </div>
      {mesob.requiredDocuments.length > 0 && (
        <div>
          <p className="mb-1 font-medium">MESOB checklist</p>
          <ul className="list-inside list-disc space-y-0.5 leading-relaxed">
            {mesob.requiredDocuments.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
        <Link href={`/services/${mesob.serviceId}`} className="text-primary underline">
          Service details
        </Link>
        <Link href={`/hire?type=guday_geday&service_id=${mesob.serviceId}`} className="text-primary underline">
          Find a licensed Guday Geday
        </Link>
        {mesob.onlineUrl && (
          <a href={mesob.onlineUrl} target="_blank" rel="noreferrer" className="text-primary underline">
            Apply online
          </a>
        )}
      </div>
      {mesob.alternatives.length > 0 && (
        <p className="text-muted-foreground">
          Also at MESOB:{" "}
          {mesob.alternatives.map((a, i) => (
            <span key={a.serviceId}>
              {i > 0 && ", "}
              <Link href={`/services/${a.serviceId}`} className="hover:underline">
                {a.serviceName}
              </Link>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

export function StepDetail({ step }: { step: RoadmapStep }) {
  if (step.orgService) {
    return (
      <div className="mt-4 space-y-4 text-xs">
        <OrgServiceBlock org={step.orgService} />
        {step.mesob && (
          <details>
            <summary className="text-muted-foreground cursor-pointer">Also available at MESOB centers</summary>
            <div className="mt-2">
              <MesobBlock mesob={step.mesob} />
            </div>
          </details>
        )}
      </div>
    );
  }
  if (!step.office) {
    return (
      <div className="mt-4 space-y-3 text-xs">
        {step.mesob ? (
          <MesobBlock mesob={step.mesob} />
        ) : (
          <p className="text-muted-foreground">
            Office details are loading. Refresh your path if this persists.
          </p>
        )}
        <ReportIssue targetType="roadmap_step" targetId={step.id} />
      </div>
    );
  }

  const office = step.office;
  const imageSrc =
    office.referenceImageUrl ??
    officeStockByStep[step.id] ??
    stockImages.officeDetail;

  const mapsUrl =
    office.latitude != null && office.longitude != null
      ? `https://www.google.com/maps/search/?api=1&query=${office.latitude},${office.longitude}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(office.address)}`;

  return (
    <div className="border-border bg-muted/20 mt-4 space-y-4 border p-4 text-xs">
      {step.mesob && <MesobBlock mesob={step.mesob} />}

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-3">
          <h4 className="font-semibold">Office</h4>
          <p className="font-medium">{office.name}</p>
          <p className="text-muted-foreground leading-relaxed">
            {office.address}
          </p>
          {office.landmark && (
            <p className="text-muted-foreground">
              Landmark: {office.landmark}
            </p>
          )}
          <p>
            <strong>Hours:</strong> {office.workingHours}
          </p>
          <p>
            <strong>Phone:</strong>{" "}
            {office.phones.map((p) => (
              <a
                key={p}
                href={`tel:${p.replace(/\s/g, "")}`}
                className="text-primary mr-2 underline"
              >
                {p}
              </a>
            ))}
          </p>
          <a
            href={mapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary inline-block underline"
          >
            Open location in Maps
          </a>
        </div>

        <div className="space-y-3">
          <h4 className="font-semibold">Office reference</h4>
          <div className="border-border relative aspect-video overflow-hidden border">
            <Image
              src={imageSrc}
              alt={`${office.name} reference`}
              fill
              className="object-cover"
              sizes="400px"
            />
          </div>
          <p className="text-muted-foreground">
            Stock reference, replace with verified photos per branch when
            available.
          </p>
        </div>
      </div>

      <Separator />

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <h4 className="mb-2 font-semibold">Fee & payment</h4>
          <p>
            <strong>Fee:</strong>{" "}
            {step.feeEtb === null
              ? "Confirm at office"
              : step.feeEtb === 0
                ? "No fee"
                : `${step.feeEtb} ETB`}
          </p>
          {(step.paymentMethods?.length ?? 0) > 0 && (
            <ul className="text-muted-foreground mt-2 list-inside list-disc space-y-1">
              {step.paymentMethods.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4 className="mb-2 font-semibold">What to prepare</h4>
          <ul className="list-inside list-disc space-y-1 leading-relaxed">
            {step.requiredInputs.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      {step.prerequisiteIds.length > 0 && (
        <>
          <Separator />
          <div>
            <h4 className="mb-2 font-semibold">Must have first</h4>
            <div className="flex flex-wrap gap-2">
              {step.prerequisiteIds.map((id) => (
                <Badge key={id} variant="outline">
                  {getDocumentLabel(id)}
                </Badge>
              ))}
            </div>
          </div>
        </>
      )}

      {step.rejectionReasons.length > 0 && (
        <>
          <Separator />
          <div>
            <h4 className="mb-2 font-semibold">Common rejection reasons</h4>
            <ul className="text-muted-foreground list-inside list-disc space-y-1">
              {step.rejectionReasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        </>
      )}

      {(step.formCode || step.legalBasis || step.sourceUrl) && (
        <p className="text-muted-foreground border-t pt-3">
          {step.formCode && <>Form: {step.formCode} · </>}
          {step.legalBasis && <>{step.legalBasis} · </>}
          {step.sourceUrl && (
            <a
              href={step.sourceUrl}
              className="text-primary underline"
              target="_blank"
              rel="noreferrer"
            >
              Official source
            </a>
          )}
        </p>
      )}
      <ReportIssue targetType="roadmap_step" targetId={step.id} />
    </div>
  );
}
