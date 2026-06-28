import { NewRoadmapForm } from "@/modules/roadmap/pages/new-roadmap-form";

type PageProps = {
  searchParams: Promise<{ goal?: string }>;
};

export default async function NewRoadmapPage({ searchParams }: PageProps) {
  const { goal } = await searchParams;
  return <NewRoadmapForm initialGoal={goal} />;
}
