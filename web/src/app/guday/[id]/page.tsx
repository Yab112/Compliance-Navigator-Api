import { redirect } from "next/navigation";

type PageProps = { params: Promise<{ id: string }> };

/** Old agent links used the id; profiles accept an id or a slug. */
export default async function AgentProfilePage({ params }: PageProps) {
  const { id } = await params;
  redirect(`/providers/${encodeURIComponent(id)}`);
}
