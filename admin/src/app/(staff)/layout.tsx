import { AdminGuard } from "@/modules/components/admin-guard";
import { AdminHeader } from "@/modules/components/admin-header";
import { AdminSidebar } from "@/modules/components/admin-sidebar";

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AdminHeader />
      <AdminGuard>
        <div className="flex min-h-[calc(100dvh-var(--nav-h))] flex-col lg:flex-row">
          {/* Stays in place while the page scrolls; long menus scroll on their own */}
          <aside className="border-border bg-muted/30 border-b lg:sticky lg:top-(--nav-h) lg:h-[calc(100dvh-var(--nav-h))] lg:w-56 lg:shrink-0 lg:self-start lg:border-r lg:border-b-0">
            <AdminSidebar />
          </aside>
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </AdminGuard>
    </>
  );
}
