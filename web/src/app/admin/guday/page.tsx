import { redirect } from "next/navigation";

export default function AdminGudayPage() {
  redirect("/admin/marketplace?type=guday_geday");
}
