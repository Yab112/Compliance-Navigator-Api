import { RoleEditorPage } from "@/modules/access/roles-page";

export default async function Page({ searchParams }: { searchParams: Promise<{ from?: string }> }) {
  const { from } = await searchParams;
  return <RoleEditorPage from={from ?? null} />;
}
