import { Suspense } from "react";
import { MySupport } from "@/modules/support/pages/my-support";

export const metadata = { title: "My support requests · Compliance Navigator" };

export default function MySupportPage() {
  return (
    <Suspense>
      <MySupport />
    </Suspense>
  );
}
