import { AdminGuard } from "@/modules/components/admin-guard";
import { AdminHeader } from "@/modules/components/admin-header";
import { AdminSidebar } from "@/modules/components/admin-sidebar";

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AdminHeader />
      <AdminGuard>
        {/* On wide screens the window never scrolls: the sidebar and the main area scroll on their own.
            Both are `relative` so hidden absolute elements (sr-only labels) stay inside them instead of
            stretching the window. */}
        <div className="flex min-h-[calc(100dvh-var(--nav-h))] flex-col lg:h-[calc(100dvh-var(--nav-h))] lg:flex-row lg:overflow-hidden">
          <aside className="relative border-border bg-muted/30 border-b lg:h-full lg:w-56 lg:shrink-0 lg:border-r lg:border-b-0">
            <AdminSidebar />
          </aside>
          <main id="staff-main" className="relative min-w-0 flex-1 lg:h-full lg:overflow-y-auto">
            {children}
          </main>
        </div>
      </AdminGuard>
    </>
  );
}
