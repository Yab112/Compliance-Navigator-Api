import Link from "next/link";
import { Button } from "@cn/ui/button";

export function RoadmapEmptyState() {
  return (
    <div className="border-border flex flex-col items-center border px-6 py-16 text-center">
      <p className="text-lg font-medium">No path yet</p>
      <p className="text-muted-foreground mt-2 max-w-sm text-sm">
        Pick passport, Kebele ID, or trade license and we will map your steps.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Link href="/roadmap/new">
          <Button size="lg">Find my path</Button>
        </Link>
        <Link href="/account/paths">
          <Button size="lg" variant="outline">My saved paths</Button>
        </Link>
      </div>
    </div>
  );
}
