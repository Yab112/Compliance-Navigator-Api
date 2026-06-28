import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, ConversationMessage } from "@/types/chat";

type RoadmapChatStore = {
  messages: ChatMessage[];
  conversationHistory: ConversationMessage[];
  addUserMessage: (text: string) => void;
  addAssistantMessage: (text: string) => void;
  updateHistory: (history: ConversationMessage[]) => void;
  clearChat: () => void;
};

export const useRoadmapChatStore = create<RoadmapChatStore>()(
  persist(
    (set) => ({
      messages: [],
      conversationHistory: [],

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

      clearChat: () => set({ messages: [], conversationHistory: [] }),
    }),
    { name: "compliance-roadmap-chat", version: 1 },
  ),
);
