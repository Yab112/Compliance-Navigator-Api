import { AdminSubmissionDetail } from "@/modules/admin/organizations/admin-submissions";

type PageProps = { params: Promise<{ id: string }> };

export default async function AdminSubmissionPage({ params }: PageProps) {
  const { id } = await params;
  return <AdminSubmissionDetail id={id} />;
}
