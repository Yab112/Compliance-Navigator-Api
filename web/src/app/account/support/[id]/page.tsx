import { MySupportTicket } from "@/modules/support/pages/my-support";

export const metadata = { title: "Support request · Compliance Navigator" };

export default async function MySupportTicketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MySupportTicket id={id} />;
}
