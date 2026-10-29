import { NewRoadmapForm } from "@/modules/roadmap/pages/new-roadmap-form";

type PageProps = {
  searchParams: Promise<{ goal?: string; sub?: string; held?: string; choice?: string }>;
};

export default async function NewRoadmapPage({ searchParams }: PageProps) {
  const { goal, sub, held, choice } = await searchParams;
  return (
    <NewRoadmapForm
      initialGoal={goal}
      initialSubCity={sub}
      initialHeld={held ? held.split(",") : undefined}
      initialChoice={choice === "agent" || choice === "self" ? choice : undefined}
    />
  );
}
