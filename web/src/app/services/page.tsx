import { Suspense } from "react";
import { ServicesBrowser } from "@/modules/catalog/pages/services-browser";

export const metadata = { title: "Services · Compliance Navigator" };

export default function ServicesPage() {
  return (
    <Suspense>
      <ServicesBrowser />
    </Suspense>
  );
}
