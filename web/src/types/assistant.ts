/** The interactive assistant (POST /assistant/turn). */

/** `label` is what the person sees as their own message when they tap a chip. */
export type AssistantAction = (
  | { type: "message"; value: string }
  | { type: "choice"; key: string; value: string }
  | { type: "documents"; value: string[] }
  | { type: "language"; value: "en" | "am" }
  | { type: "ask"; value: string }
  | { type: "hire" }
  | { type: "start_over" }
  | { type: "form"; key: string; value: Record<string, string> }
  | { type: "confirm"; value: string }
  | { type: "cancel_task" }
  | { type: "handoff" }
  | { type: "channel"; value: "agent" | "human" }
) & { label?: string };

export type QuickReply = { label: string; action: AssistantAction };

export type WidgetOption = { value: string; label: string };

export type FormField = {
  key: string;
  label: string;
  type: "text" | "tel" | "email" | "textarea";
  required: boolean;
  value?: string | null;
  placeholder?: string | null;
};

export type AssistantWidget =
  | {
      kind: "choice" | "sub_city" | "checklist";
      key: string;
      options: WidgetOption[];
      submit_label?: string;
      none_label?: string;
      selected?: string[];
    }
  | { kind: "form"; key: string; fields: FormField[]; submit_label?: string };

export type PathStepCard = {
  title: string;
  office?: string | null;
  fee?: string | null;
  time?: string | null;
  documents: string[];
  mesob?: { service?: string; fee?: string; time?: string } | null;
};

export type AssistantCard =
  | {
      kind: "service";
      title: string;
      provider?: string | null;
      source: "organization" | "path" | "mesob";
      fee?: string | null;
      time?: string | null;
      documents: (string | { label: string; done: boolean })[];
      href?: string | null;
    }
  | { kind: "path"; title: string; href?: string | null; steps: PathStepCard[] }
  | {
      kind: "checklist";
      title: string;
      /** "list": a plain record (jobs, reviews), nothing to tick off */
      style?: "list";
      items: { label: string; done: boolean; detail?: string | null }[];
    }
  | {
      kind: "branches";
      items: { name: string; address?: string | null; hours?: string | null; window?: string | null; phone?: string | null; map_url?: string | null }[];
    }
  | {
      kind: "providers";
      href: string;
      items: {
        name: string;
        slug: string;
        headline?: string | null;
        type?: string | null;
        score?: number | null;
        rating?: number | null;
        reviews?: number | null;
        photo?: string | null;
        verified?: boolean;
      }[];
    }
  | { kind: "summary"; title: string; rows: { label: string; value: string }[] }
  | {
      kind: "ticket";
      id: string;
      ref: string;
      subject: string;
      queue_label: string;
      status: string;
      status_label: string;
      priority: string;
      expected?: string | null;
      href?: string | null;
    }
  | {
      kind: "status";
      items: { kind: "ticket" | "hire" | "path"; title: string; status_label: string; href?: string | null; updated_at?: string | null }[];
    };

export type ReplyAction =
  | { kind: "link"; label: string; href: string }
  | { kind: "action"; label: string; action: AssistantAction };

export type AssistantReply = {
  text: string;
  quick_replies: QuickReply[];
  widget: AssistantWidget | null;
  cards: AssistantCard[];
  actions: ReplyAction[];
  source: string | null;
  intent?: string | null;
  confidence?: number | null;
};

export type StaffAuthor = { name?: string | null; team?: string | null };

export type AssistantMessage =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; reply: AssistantReply }
  | { id: string; role: "staff"; text: string; staff: StaffAuthor; createdAt?: string };

export type AssistantChannel = "agent" | "human";

/** The support request this conversation was handed to, if any. */
export type ConversationTicket = { id: string; ref: string; status: string; status_label: string; queue_label: string };

/** GET /assistant/conversations/{id} message rows. */
export type ServerMessage = {
  id: number;
  role: "user" | "assistant" | "staff";
  text: string;
  reply?: AssistantReply | null;
  staff?: StaffAuthor | null;
  createdAt?: string;
};

export type TurnResult = {
  conversationId: string;
  language: "en" | "am";
  /** null when the message went to a person (channel "human") */
  reply: AssistantReply | null;
  delivered?: boolean;
  channel?: AssistantChannel;
  ticket?: ConversationTicket | null;
  service: { key: string; source: string; title: string; title_am?: string | null } | null;
  subCity: string | null;
  held: string[];
};
