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
  /** First-reply target */
  sla_due_at: string;
  /** When we owe the customer an answer now; null when it's their turn or the request ended */
  next_response_due_at?: string | null;
  overdue: boolean;
  last_message_preview?: string | null;
  last_message_at?: string | null;
  awaiting_staff: boolean;
  /** Who has to act next on an active request */
  waiting_on?: "us" | "customer" | null;
  waiting_since?: string | null;
  /** A resolved or closed request reopens when the customer replies before reopen_until */
  can_reopen?: boolean;
  reopen_until?: string | null;
  /** The older request this one follows up */
  follow_up_of?: string | null;
  follow_up_of_ref?: string | null;
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
  follow_up_of?: string;
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
  /** Delivered hires unpaid this long show as "deals to follow up" */
  follow_up_hours: number;
};

export type AdminTicketDetail = TicketThread & {
  transcript: { role: "user" | "assistant" | "staff"; text: string; created_at: string }[];
  staff: { id: string; name: string }[];
};

export type TicketSort = "triage" | "newest" | "oldest" | "updated";

/** Desk list and CSV export filters (the API's query string). */
export type TicketFilters = {
  queue?: string;
  status?: string;
  /** "me", "none" or a staff id */
  assigned?: string;
  priority?: string;
  source?: string;
  waiting?: "us" | "customer";
  q?: string;
  since?: string;
  until?: string;
  sort?: TicketSort;
  limit?: number;
  offset?: number;
};

/** Who is behind a ticket: only what the desk needs. Hires and payments are null when hidden. */
export type CustomerContext = {
  account: {
    id: string;
    name: string;
    email: string;
    phone?: string | null;
    role: string;
    is_active: boolean;
    created_at: string;
    last_login_at?: string | null;
    roadmaps: number;
  } | null;
  provider: { id: string; display_name: string; status: string; provider_type?: string | null } | null;
  hires: {
    items: {
      id: string;
      title: string;
      status: string;
      payment_status?: string | null;
      disputed?: boolean | null;
      dispute_status?: string | null;
      agreed_price?: number | string | null;
      created_at: string;
      provider_name?: string | null;
    }[];
    total: number;
  } | null;
  payments: {
    items: {
      tx_ref: string;
      amount: number | string;
      currency: string;
      status: string;
      created_at: string;
      verified_at?: string | null;
      hire_title?: string | null;
    }[];
    total: number;
  } | null;
  tickets: {
    items: { id: string; ref: string; subject: string; status: TicketStatus; status_label: string; queue: SupportQueue; queue_label: string; created_at: string }[];
    total: number;
  };
  /** Sections left out because this staff member lacks the permission */
  hidden: ("hires" | "payments")[];
};

export type CannedReply = {
  id: string;
  title: string;
  body: string;
  queue?: SupportQueue | null;
  queue_label?: string | null;
  use_count: number;
  created_by_name?: string | null;
  updated_by_name?: string | null;
  created_at: string;
  updated_at: string;
  /** Filled in for one ticket (when listed with ticket_id) */
  rendered?: string;
};

export type CannedReplyInput = { title: string; body: string; queue?: SupportQueue | null };

export type CannedReplyList = { items: CannedReply[]; total: number; placeholders: Record<string, string> };

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
