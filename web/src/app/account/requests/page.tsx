import { Suspense } from "react";
import { MyRequests } from "@/modules/account/pages/my-requests";

export const metadata = { title: "My hires · Compliance Navigator" };

export default function MyRequestsPage() {
  return (
    <Suspense>
      <MyRequests />
    </Suspense>
  );
}
