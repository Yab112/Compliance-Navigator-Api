import { Workspace } from "@/modules/organizations/pages/workspace";

type PageProps = { params: Promise<{ orgId: string }> };

export default async function OrgWorkspacePage({ params }: PageProps) {
  const { orgId } = await params;
  return <Workspace orgId={orgId} />;
}
