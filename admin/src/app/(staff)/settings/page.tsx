import { Suspense } from "react";
import { SettingsPage } from "@/modules/settings/settings-page";

export default function AdminSettingsPage() {
  return (
    <Suspense>
      <SettingsPage />
    </Suspense>
  );
}
