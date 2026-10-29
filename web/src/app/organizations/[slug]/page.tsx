import { OrganizationProfile } from "@/modules/organizations/pages/org-profile";

type PageProps = { params: Promise<{ slug: string }> };

export default async function OrganizationPage({ params }: PageProps) {
  const { slug } = await params;
  return <OrganizationProfile slug={slug} />;
}
