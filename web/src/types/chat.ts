import type { Roadmap } from "./roadmap";

export type ConversationMessage = {
  role: "user" | "assistant";
  content: string | object[];
};

export type ChatRequest = {
  message: string;
  roadmap_id?: string | null;
  documents_held: string[];
  sub_city?: string | null;
  goal?: string | null;
  sector?: string | null;
  industry?: string | null;
  conversation_history: ConversationMessage[];
};

export type ChatResponse = {
  reply: string;
  needs_more_info: boolean;
  missing_slots: string[];
  suggested_goal: string | null;
  suggested_sub_city: string | null;
  suggested_documents_held: string[];
  intent: string;
  language: string;
  roadmap: Roadmap | null;
  updated_history: ConversationMessage[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: number;
};

export type AccumulatedSlots = {
  goal: string | null;
  sub_city: string | null;
  documents_held: string[];
};

export type TranscribeResponse = {
  text: string;
  detected_language: string;
};
