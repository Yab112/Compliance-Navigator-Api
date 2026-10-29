import { ProviderProfile } from "@/modules/marketplace/pages/provider-profile";

export default async function ProviderPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <ProviderProfile slug={slug} />;
}
