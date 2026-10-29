import { Suspense } from "react";
import { AdminReviews } from "@/modules/admin/marketplace/admin-hires";

export default function AdminReviewsPage() {
  return (
    <Suspense>
      <AdminReviews />
    </Suspense>
  );
}
