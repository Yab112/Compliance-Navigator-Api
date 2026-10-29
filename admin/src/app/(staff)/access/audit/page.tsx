import { Suspense } from "react";
import { AuditPage } from "@/modules/access/audit-page";

export default function Page() {
  return (
    <Suspense>
      <AuditPage />
    </Suspense>
  );
}
