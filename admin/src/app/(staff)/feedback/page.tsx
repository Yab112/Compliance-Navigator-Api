import { Suspense } from "react";
import { FeedbackPage } from "@/modules/feedback/feedback-page";

export default function AdminFeedbackRoute() {
  return (
    <Suspense>
      <FeedbackPage />
    </Suspense>
  );
}
