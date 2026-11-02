import { Suspense } from "react";
import { MyReminders } from "@/modules/account/pages/my-reminders";

export const metadata = { title: "My reminders · Compliance Navigator" };

export default function MyRemindersPage() {
  return (
    <Suspense>
      <MyReminders />
    </Suspense>
  );
}
