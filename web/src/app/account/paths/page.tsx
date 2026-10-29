import { Suspense } from "react";
import { SavedPaths } from "@/modules/roadmap/pages/saved-paths";

export const metadata = { title: "My saved paths · Compliance Navigator" };

export default function SavedPathsPage() {
  return (
    <Suspense>
      <SavedPaths />
    </Suspense>
  );
}
