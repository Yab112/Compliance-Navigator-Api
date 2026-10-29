import { AdminProviderDetail } from "@/modules/admin/marketplace/admin-provider-detail";

export default async function AdminProviderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AdminProviderDetail id={id} />;
}
