import type { Metadata } from "next";
import { env } from "@cn/core/config/env";
import { ProviderProfile } from "@/modules/marketplace/pages/provider-profile";

type PageProps = { params: Promise<{ slug: string }> };

/** The provider's name in the tab title. Unlisted or missing profiles (404) get a plain title. */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const fallback = { title: "Provider profile · Compliance Navigator" };
  try {
    const res = await fetch(`${env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")}/providers/${encodeURIComponent(slug)}`, {
      next: { revalidate: 300 },
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return fallback;
    const name = (await res.json())?.payload?.provider?.display_name;
    return typeof name === "string" && name ? { title: `${name} · Compliance Navigator` } : fallback;
  } catch {
    return fallback;
  }
}

export default async function ProviderPage({ params }: PageProps) {
  const { slug } = await params;
  return <ProviderProfile slug={slug} />;
}
