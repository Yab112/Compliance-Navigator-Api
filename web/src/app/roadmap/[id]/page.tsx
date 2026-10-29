import { SavedRoadmap } from "@/modules/roadmap/pages/saved-roadmap";

export default async function SavedRoadmapPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SavedRoadmap id={id} />;
}
