import type { AgentEvent } from "@/types/guday";
import { formatDateTime } from "./shared";

const ACTION_LABEL: Record<string, string> = {
  registered: "Application submitted",
  resubmitted: "Application resubmitted",
  updated: "Profile updated",
  approve: "Approved & licensed",
  reject: "Rejected",
  suspend: "Suspended",
  reinstate: "Reinstated",
  renew: "License renewed",
  core_details_changed: "Legal details changed, sent for re-review",
  member_requested: "Member asked to join",
  member_invited: "Member invited",
  member_active: "Member added",
  member_declined: "Membership declined",
  member_removed: "Member removed",
  license_verified: "Sector licence verified",
  license_rejected: "Sector licence rejected",
  review_hidden: "Review hidden",
  review_restored: "Review restored",
  complaint_upheld: "Complaint upheld",
  complaint_dismissed: "Complaint dismissed",
};

export function EventLog({
  events,
  showActor = false,
  labels,
}: {
  events: AgentEvent[];
  showActor?: boolean;
  /** Per-registry wording, e.g. organizations are "verified" not "licensed" */
  labels?: Record<string, string>;
}) {
  if (events.length === 0) return <p className="text-muted-foreground text-xs">No activity yet.</p>;
  return (
    <ol className="border-border space-y-3 border-l pl-4">
      {events.map((e) => (
        <li key={e.id} className="relative text-xs">
          <span className="bg-primary absolute top-1 -left-[19px] size-2" aria-hidden />
          <p className="font-medium">{labels?.[e.action] ?? ACTION_LABEL[e.action] ?? e.action}</p>
          {e.note && <p className="text-muted-foreground mt-0.5 leading-relaxed">{e.note}</p>}
          <p className="text-muted-foreground mt-0.5 text-[11px]">
            {formatDateTime(e.created_at)}
            {showActor && e.actor ? ` · ${e.actor}` : ""}
          </p>
        </li>
      ))}
    </ol>
  );
}
