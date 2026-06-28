import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, AccumulatedSlots, ConversationMessage } from "@/types/chat";

const INITIAL_SLOTS: AccumulatedSlots = {
  goal: null,
  sub_city: null,
  documents_held: [],
};

type ChatStore = {
  messages: ChatMessage[];
  conversationHistory: ConversationMessage[];
  slots: AccumulatedSlots;
  addUserMessage: (text: string) => void;
  addAssistantMessage: (text: string) => void;
  updateHistory: (history: ConversationMessage[]) => void;
  updateSlots: (partial: Partial<AccumulatedSlots>) => void;
  clearChat: () => void;
};

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      messages: [],
      conversationHistory: [],
      slots: INITIAL_SLOTS,

      addUserMessage: (text) =>
        set((state) => ({
          messages: [
            ...state.messages,
            { id: `u-${Date.now()}`, role: "user", text, timestamp: Date.now() },
          ],
        })),

      addAssistantMessage: (text) =>
        set((state) => ({
          messages: [
            ...state.messages,
            { id: `a-${Date.now()}`, role: "assistant", text, timestamp: Date.now() },
          ],
        })),

      updateHistory: (history) => set({ conversationHistory: history }),

      updateSlots: (partial) =>
        set((state) => ({
          slots: {
            ...state.slots,
            ...partial,
            documents_held:
              partial.documents_held !== undefined
                ? partial.documents_held
                : state.slots.documents_held,
          },
        })),

      clearChat: () =>
        set({ messages: [], conversationHistory: [], slots: INITIAL_SLOTS }),
    }),
    { name: "compliance-chat", version: 1 },
  ),
);
