import { redirect } from "next/navigation";

export default function GudayRegisterPage() {
  redirect("/providers/join?type=guday_geday");
}
