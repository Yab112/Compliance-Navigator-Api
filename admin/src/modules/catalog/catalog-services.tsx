"use client";

import { siteUrl } from "@cn/core/config/env";
import { useEffect, useId, useState } from "react";
import { Button, buttonVariants } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { Pager } from "@cn/ui/pager";
import { useAdminQuery } from "@cn/core/api/admin";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import type { Paged } from "@cn/core/types/guday";
import type { CatalogService } from "@cn/core/types/catalog";
import { NativeSelect } from "@/modules/shared/native-select";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";

const PAGE_SIZE = 20;

type Props = {
  institution: { id: string; name: string } | null;
  onClearInstitution: () => void;
};

/** Every service in the MESOB snapshot, searched and paged on the server. */
export function CatalogServices({ institution, onClearInstitution }: Props) {
  const uid = useId();
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [language, setLanguage] = useState<"en" | "am">("en");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const institutionId = institution?.id ?? "";
  const [lastInstitution, setLastInstitution] = useState(institutionId);
  if (lastInstitution !== institutionId) {
    // A new institution was picked in the table: start from its first page
    setLastInstitution(institutionId);
    setPage(0);
  }

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(input.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [input]);

  const params = new URLSearchParams({ language, limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) });
  if (q) params.set("q", q);
  if (institutionId) params.set("institution_id", institutionId);
  const services = useAdminQuery<Paged<CatalogService>>(
    ["catalog-services", q, language, institutionId, page],
    `${apiPaths.catalog.services}?${params}`,
  );
  const items = services.payload?.items ?? [];

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex flex-1 flex-col gap-1.5">
          <Label htmlFor={`${uid}-q`}>Search services</Label>
          <Input
            id={`${uid}-q`}
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Service name, institution or required document"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${uid}-lang`}>Language</Label>
          <NativeSelect
            id={`${uid}-lang`}
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value as "en" | "am");
              setPage(0);
            }}
          >
            <option value="en">English</option>
            <option value="am">Amharic · አማርኛ</option>
          </NativeSelect>
        </div>
      </div>
      {institution && (
        <p className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">Only services from</span>
          <span className="font-medium">{institution.name}</span>
          <Button size="sm" variant="outline" onClick={onClearInstitution}>
            Show all institutions
          </Button>
        </p>
      )}

      {services.isLoading ? (
        <LoadingState />
      ) : services.error ? (
        <ErrorState message={getErrorMessage(services.error)} onRetry={() => services.refetch()} />
      ) : !items.length ? (
        <EmptyState
          title="No services match"
          description={q || institution ? "Try other words, or show all institutions." : "The snapshot has no services. Refresh it from the button at the top."}
        />
      ) : (
        <ul className={cn("divide-border divide-y text-xs", services.isFetching && "opacity-60")}>
          {items.map((s) => {
            const expanded = open === s.id;
            return (
              <li key={s.id} className="py-2">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                  <div className="min-w-0">
                    <p className="font-medium break-words">{s.name}</p>
                    <p className="text-muted-foreground text-[11px]">
                      {s.institution.short_name ?? s.institution.name ?? s.institution_id}
                      {" · "}
                      {s.fee_text || "Fee not listed"}
                      {" · "}
                      {s.processing_time_text || "Time not listed"}
                      {" · "}
                      {s.required_documents.length} required document{s.required_documents.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-expanded={expanded}
                      aria-controls={`${uid}-${s.id}`}
                      onClick={() => setOpen(expanded ? null : s.id)}
                    >
                      {expanded ? "Hide details" : "Details"}
                    </Button>
                    <a
                      href={siteUrl(`/services/${s.id}`)}
                      target="_blank"
                      rel="noreferrer"
                      className={buttonVariants({ size: "sm", variant: "outline" })}
                    >
                      Public page
                    </a>
                  </div>
                </div>
                {expanded && (
                  <div id={`${uid}-${s.id}`} className="border-border bg-muted/20 mt-2 space-y-2 border p-2">
                    {s.required_documents.length > 0 ? (
                      <div>
                        <p className="text-muted-foreground mb-0.5 text-[11px]">Required documents</p>
                        <ul className="list-inside list-disc">
                          {s.required_documents.map((d, i) => (
                            <li key={i} className="break-words">
                              {d}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <p className="text-muted-foreground">MESOB lists no required documents for this service.</p>
                    )}
                    <p className="flex flex-wrap gap-x-4 gap-y-1">
                      {s.online_url && (
                        <a href={s.online_url} target="_blank" rel="noreferrer" className="text-primary underline">
                          Apply online
                        </a>
                      )}
                      {s.source_url && (
                        <a href={s.source_url} target="_blank" rel="noreferrer" className="text-primary underline">
                          Source on mesobcenter.et
                        </a>
                      )}
                    </p>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <Pager page={page} pageSize={PAGE_SIZE} total={services.payload?.total ?? 0} onPage={setPage} />
    </div>
  );
}
