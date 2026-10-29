import { Suspense } from "react";
import { FaydaCallbackPage } from "@/modules/guday/pages/fayda-pages";

export const metadata = { title: "Verifying with Fayda · Compliance Navigator" };

export default function Page() {
  return (
    <Suspense>
      <FaydaCallbackPage />
    </Suspense>
  );
}
