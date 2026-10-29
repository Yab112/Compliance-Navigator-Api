import { ServiceEditor } from "@/modules/organizations/pages/service-editor";

type PageProps = { params: Promise<{ orgId: string }> };

export default async function NewServicePage({ params }: PageProps) {
  const { orgId } = await params;
  return <ServiceEditor orgId={orgId} serviceId={null} />;
}
