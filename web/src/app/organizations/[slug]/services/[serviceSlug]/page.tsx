import { ServicePage } from "@/modules/organizations/pages/service-page";

type PageProps = { params: Promise<{ slug: string; serviceSlug: string }> };

export default async function OrganizationServicePage({ params }: PageProps) {
  const { slug, serviceSlug } = await params;
  return <ServicePage slug={slug} serviceSlug={serviceSlug} />;
}
