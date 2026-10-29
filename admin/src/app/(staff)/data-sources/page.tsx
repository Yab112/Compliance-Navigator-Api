import { Suspense } from "react";
import { DataSourcesPage } from "@/modules/data-sources/data-sources-page";

export default function AdminDataSourcesRoute() {
  return (
    <Suspense>
      <DataSourcesPage />
    </Suspense>
  );
}
