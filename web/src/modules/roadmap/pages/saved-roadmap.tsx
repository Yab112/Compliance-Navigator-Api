"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useGetRoadmap } from "@/api/roadmap";
import { LoadingState } from "@cn/ui/guday/shared";
import { RoadmapView } from "@/modules/roadmap/pages/roadmap-view";
import { useRoadmapStore } from "@/store/roadmap-store";
import { useUserStore } from "@/store";

/** /roadmap/[id]: open a saved path from the server (links from My saved paths and the assistant). */
export function SavedRoadmap({ id }: { id: string }) {
  const status = useUserStore((s) => s.status);
  const { roadmap, isLoading, isError } = useGetRoadmap(id, status !== "loading");
  const current = useRoadmapStore((s) => s.current);
  const setCurrent = useRoadmapStore((s) => s.setCurrent);

  useEffect(() => {
    if (roadmap) setCurrent(roadmap);
  }, [roadmap, setCurrent]);

  if (isError) {
    return (
      <div className="mx-auto max-w-lg px-4 py-20 text-center">
        <p className="text-lg font-medium">This path isn&apos;t available</p>
        <p className="text-muted-foreground mt-2 text-sm">
          It may have been removed, or it was saved to another account. Sign in with the account that saved it.
        </p>
        <div className="mt-6 flex justify-center gap-2 text-sm">
          <Link href="/account/paths" className="border-border rounded-md border px-4 py-2">My saved paths</Link>
          <Link href="/roadmap/new" className="bg-primary text-primary-foreground rounded-md px-4 py-2 font-semibold">Find my path</Link>
        </div>
      </div>
    );
  }
  if (isLoading || status === "loading" || !current || current.id !== id) return <LoadingState label="Opening your path…" />;
  return <RoadmapView />;
}
