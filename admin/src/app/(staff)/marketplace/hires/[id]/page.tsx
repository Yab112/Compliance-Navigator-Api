import { AdminHireDetail } from "@/modules/marketplace/admin-hire-detail";

export default async function AdminHirePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AdminHireDetail id={id} />;
}
