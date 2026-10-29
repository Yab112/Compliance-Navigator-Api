"use client";

import { useState } from "react";
import { useReportIssue, type FeedbackTarget } from "@/api/feedback";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";

type ReportIssueProps = {
  targetType: FeedbackTarget;
  targetId?: string;
  label?: string;
  className?: string;
};

/** "This information is wrong", lands in the admin feedback queue. */
export function ReportIssue({
  targetType,
  targetId,
  label = "Report incorrect info",
  className,
}: ReportIssueProps) {
  const { report, isReporting } = useReportIssue();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <p className={cn("text-muted-foreground text-xs", className)}>
        Thanks. Our team will review your report.
      </p>
    );
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn("text-muted-foreground text-xs underline hover:text-foreground", className)}
      >
        {label}
      </button>
    );
  }

  return (
    <form
      className={cn("border-border flex flex-col gap-2 border p-3", className)}
      onSubmit={async (e) => {
        e.preventDefault();
        if (message.trim().length < 5) {
          setError("Please describe what is wrong (at least 5 characters).");
          return;
        }
        setError(null);
        try {
          await report({ target_type: targetType, target_id: targetId, message: message.trim() });
          setSent(true);
        } catch (err) {
          setError(getErrorMessage(err, "Could not send your report"));
        }
      }}
    >
      <label htmlFor={`report-${targetType}-${targetId}`} className="text-xs font-medium">
        What is incorrect?
      </label>
      <Textarea
        id={`report-${targetType}-${targetId}`}
        value={message}
        maxLength={1000}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="e.g. The fee changed to 150 ETB last month"
      />
      {error && <p className="text-destructive text-xs">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={isReporting}>
          Send report
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
