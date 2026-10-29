/** Support desk: tickets raised from the assistant, the contact form or a report. */

export type SupportQueue = "customer_support" | "compliance" | "marketplace" | "organizations" | "technical";
export type TicketStatus = "new" | "open" | "waiting_customer" | "resolved" | "closed";
export type TicketPriority = "low" | "normal" | "high" | "urgent";
export type TicketSource = "assistant" | "contact_form" | "report";

export type TicketContext = {
  service?: string | null;
  sub_city?: string | null;
  held?: string[];
  answers?: Record<string, unknown>;
  language?: string | null;
  summary?: string | null;
};

export type SupportTicket = {
  id: string;
  ref: string;
  subject: string;
  queue: SupportQueue;
  queue_label: string;
  status: TicketStatus;
  status_label: string;
  priority: TicketPriority;
  source: TicketSource;
  category?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  user_id?: string | null;
  user_email?: string | null;
  conversation_id?: string | null;
  service_key?: string | null;
  service_title?: string | null;
  context?: TicketContext | null;
  assignee_id?: string | null;
  assignee_name?: string | null;
  created_at: string;
  updated_at: string;
  first_response_at?: string | null;
  resolved_at?: string | null;
  sla_due_at: string;
  overdue: boolean;
  last_message_preview?: string | null;
  last_message_at?: string | null;
  awaiting_staff: boolean;
  message_count: number;
};

export type TicketMessage = {
  id: string | number;
  author_kind: "customer" | "staff" | "system" | "assistant";
  author_name?: string | null;
  body: string;
  internal: boolean;
  created_at: string;
};

export type TicketThread = { ticket: SupportTicket; messages: TicketMessage[] };

export type SupportMeta = {
  queues: { key: SupportQueue; label: string; label_am?: string | null; description?: string | null }[];
  contact: {
    phone?: string | null;
    email?: string | null;
    hours?: string | null;
    hours_am?: string | null;
    address?: string | null;
    address_am?: string | null;
  };
};

export type NewTicketInput = {
  queue?: SupportQueue;
  subject: string;
  body: string;
  name?: string;
  phone?: string;
  email?: string;
  conversation_id?: string;
};

export type SupportSummary = {
  totals: {
    new: number;
    open: number;
    waiting_customer: number;
    overdue: number;
    unassigned: number;
    mine: number;
    resolved_7d: number;
    avg_first_response_minutes: number | null;
  };
  queues: { key: SupportQueue; label: string; open: number; unassigned: number; overdue: number }[];
  related: {
    hires_unmatched: number;
    deals_to_follow_up: number;
    wrong_info_reports: number;
    providers_pending: number;
    org_submissions_pending: number;
  };
};

export type AdminTicketDetail = TicketThread & {
  transcript: { role: "user" | "assistant" | "staff"; text: string; created_at: string }[];
  staff: { id: string; name: string }[];
};

export type TicketPatch = {
  status?: TicketStatus;
  priority?: TicketPriority;
  queue?: SupportQueue;
  assignee_id?: string | null;
};

export const QUEUE_LABELS: Record<SupportQueue, string> = {
  customer_support: "General help",
  compliance: "Compliance and requirements",
  marketplace: "Providers and hires",
  organizations: "Organizations and service data",
  technical: "Account and website",
};

export const STATUS_LABELS: Record<TicketStatus, string> = {
  new: "New",
  open: "Open",
  waiting_customer: "Waiting on customer",
  resolved: "Resolved",
  closed: "Closed",
};

export const PRIORITY_LABELS: Record<TicketPriority, string> = {
  low: "Low",
  normal: "Normal",
  high: "High",
  urgent: "Urgent",
};
