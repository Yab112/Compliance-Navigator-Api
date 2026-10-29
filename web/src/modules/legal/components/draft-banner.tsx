import { LEGAL_DRAFT, LEGAL_DRAFT_NOTICE, LEGAL_DRAFT_NOTICE_AM } from "@/content/legal";
import { cn } from "@cn/core/lib/utils";

/** "Draft, to be reviewed by an Ethiopian lawyer". Turned off for every page by LEGAL_DRAFT. */
export function DraftBanner({ className }: { className?: string }) {
  if (!LEGAL_DRAFT) return null;
  return (
    <p
      role="note"
      className={cn("rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900", className)}
    >
      <strong>{LEGAL_DRAFT_NOTICE}</strong> <span lang="am">{LEGAL_DRAFT_NOTICE_AM}</span>
    </p>
  );
}
