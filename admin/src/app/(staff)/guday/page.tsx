import { redirect } from "next/navigation";

export default function AdminGudayPage() {
  redirect("/marketplace?type=guday_geday");
}
