import { Suspense } from "react";
import { FeedbackPage } from "@/modules/admin/feedback/feedback-page";

export default function AdminFeedbackRoute() {
  return (
    <Suspense>
      <FeedbackPage />
    </Suspense>
  );
}
