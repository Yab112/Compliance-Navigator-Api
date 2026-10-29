import { SupportTicketDetail } from "@/modules/support/support-ticket";

export default async function AdminSupportTicketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SupportTicketDetail id={id} />;
}
