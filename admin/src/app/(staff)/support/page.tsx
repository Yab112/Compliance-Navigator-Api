import { Suspense } from "react";
import { SupportDesk } from "@/modules/support/support-desk";

export default function AdminSupportPage() {
  return (
    <Suspense>
      <SupportDesk />
    </Suspense>
  );
}
