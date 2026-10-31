import { AdminGuard } from "@/modules/components/admin-guard";
import { AdminHeader } from "@/modules/components/admin-header";
import { AdminTopNav } from "@/modules/components/admin-top-nav";

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AdminHeader />
      <AdminGuard>
        <AdminTopNav />
        <main id="staff-main" className="relative min-w-0">
          {children}
        </main>
      </AdminGuard>
    </>
  );
}
