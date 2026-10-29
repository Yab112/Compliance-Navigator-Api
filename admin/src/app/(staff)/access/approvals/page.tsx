import { Suspense } from "react";
import { ApprovalsPage } from "@/modules/access/approvals-page";

export default function Page() {
  return (
    <Suspense>
      <ApprovalsPage />
    </Suspense>
  );
}
