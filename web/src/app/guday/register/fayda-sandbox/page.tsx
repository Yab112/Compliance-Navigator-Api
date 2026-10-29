import { Suspense } from "react";
import { FaydaSandboxPage } from "@/modules/guday/pages/fayda-pages";

export const metadata = { title: "Fayda test mode · Compliance Navigator" };

export default function Page() {
  return (
    <Suspense>
      <FaydaSandboxPage />
    </Suspense>
  );
}
