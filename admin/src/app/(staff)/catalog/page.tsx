import { Suspense } from "react";
import { CatalogPage } from "@/modules/catalog/catalog-page";

export default function AdminCatalogRoute() {
  return (
    <Suspense>
      <CatalogPage />
    </Suspense>
  );
}
