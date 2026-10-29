import { AdminOrganizationDetail } from "@/modules/organizations/admin-organizations";

type PageProps = { params: Promise<{ id: string }> };

export default async function AdminOrganizationPage({ params }: PageProps) {
  const { id } = await params;
  return <AdminOrganizationDetail id={id} />;
}
