import { StaffDetailPage } from "@/modules/access/staff-detail";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StaffDetailPage id={id} />;
}
