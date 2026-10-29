import type { Metadata } from "next";
import { AdminGuard } from "@/modules/admin/components/admin-guard";
import { AdminSidebar } from "@/modules/admin/components/admin-sidebar";

export const metadata: Metadata = {
  title: "Admin · Compliance Navigator",
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminGuard>
      <div className="flex min-h-[calc(100dvh-var(--nav-h))] flex-col lg:flex-row">
        <aside className="border-border bg-muted/30 border-b lg:w-56 lg:shrink-0 lg:border-r lg:border-b-0">
          <AdminSidebar />
        </aside>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </AdminGuard>
  );
}
