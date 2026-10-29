import { Suspense } from "react";
import { CannedReplies } from "@/modules/support/canned-replies";

export default function SupportRepliesPage() {
  return (
    <Suspense>
      <CannedReplies />
    </Suspense>
  );
}
