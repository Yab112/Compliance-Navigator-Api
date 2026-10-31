import { redirect } from "next/navigation";

// /access has no page of its own; staff is the first tab
export default function Page() {
  redirect("/access/staff");
}
