import type { Metadata } from "next";
import { LegalIndexPage } from "@/modules/legal/pages/legal-index";

export const metadata: Metadata = { title: "Legal · Compliance Navigator" };

export default function Page() {
  return <LegalIndexPage />;
}
