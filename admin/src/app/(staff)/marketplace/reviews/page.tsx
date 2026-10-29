import { Suspense } from "react";
import { AdminReviews } from "@/modules/marketplace/admin-hires";

export default function AdminReviewsPage() {
  return (
    <Suspense>
      <AdminReviews />
    </Suspense>
  );
}
