import { ServiceEditor } from "@/modules/organizations/pages/service-editor";

type PageProps = { params: Promise<{ orgId: string; serviceId: string }> };

export default async function EditServicePage({ params }: PageProps) {
  const { orgId, serviceId } = await params;
  return <ServiceEditor key={serviceId} orgId={orgId} serviceId={serviceId} />;
}
