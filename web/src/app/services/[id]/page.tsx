import { ServiceDetail } from "@/modules/catalog/pages/service-detail";

type PageProps = { params: Promise<{ id: string }> };

export default async function ServiceDetailPage({ params }: PageProps) {
  const { id } = await params;
  return <ServiceDetail id={id} />;
}
