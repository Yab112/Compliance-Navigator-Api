"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@cn/core/lib/api";
import { getErrorMessage } from "@cn/core/lib/errors";
import type { APIResponse } from "@cn/core/types/global";
import type {
  AssistantAction,
  AssistantChannel,
  AssistantMessage,
  AssistantReply,
  ConversationTicket,
  ServerMessage,
  TurnResult,
} from "@/types/assistant";

const STORAGE_PREFIX = "cn-assistant:";
const POLL_MS = 15_000;
const CLOSED = new Set(["resolved", "closed"]);

type ConversationPayload = {
  conversationId: string;
  language: "en" | "am";
  messages: ServerMessage[];
  channel?: AssistantChannel;
  ticket?: ConversationTicket | null;
};

function storedId(scope: string): string | null {
  try {
    return localStorage.getItem(STORAGE_PREFIX + scope);
  } catch {
    return null;
  }
}

function storeId(scope: string, id: string | null) {
  try {
    if (id) localStorage.setItem(STORAGE_PREFIX + scope, id);
    else localStorage.removeItem(STORAGE_PREFIX + scope);
  } catch {}
}

let counter = 0;
const nextId = () => `m${Date.now()}-${counter++}`;

function actionLabel(action: AssistantAction): string {
  if (action.label) return action.label;
  switch (action.type) {
    case "message":
      return action.value;
    case "documents":
      return action.value.length ? `${action.value.length} selected` : "None";
    case "language":
      return action.value === "am" ? "አማርኛ" : "English";
    case "handoff":
      return "Talk to a person";
    case "channel":
      return action.value === "agent" ? "Back to the assistant" : "Talk to a person";
    case "cancel_task":
      return "Cancel";
    case "form":
      return Object.values(action.value).filter(Boolean).join(" · ");
    default:
      return "";
  }
}

function fromServer(m: ServerMessage): AssistantMessage {
  if (m.role === "assistant" && m.reply) return { id: `s${m.id}`, role: "assistant", reply: m.reply };
  if (m.role === "staff") return { id: `s${m.id}`, role: "staff", text: m.text, staff: m.staff ?? {}, createdAt: m.createdAt };
  return { id: `s${m.id}`, role: "user", text: m.text };
}

/**
 * One conversation with the assistant, kept on the server. `scope` separates the Ask page
 * from the roadmap side panels; the conversation id survives reloads in localStorage.
 * Once the conversation is handed to a person, staff replies are polled into the thread.
 */
export function useAssistant(
  scope: string,
  options: { onTurn?: (result: TurnResult) => void; contextService?: string | null } = {},
) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [language, setLanguage] = useState<"en" | "am">("en");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [channel, setChannel] = useState<AssistantChannel>("agent");
  const [ticket, setTicket] = useState<ConversationTicket | null>(null);
  const conversationId = useRef<string | null>(null);
  // Highest server message id seen, for ?after= polling
  const lastServerId = useRef(0);
  const onTurn = useRef(options.onTurn);
  useEffect(() => {
    onTurn.current = options.onTurn;
  }, [options.onTurn]);

  const seen = (rows: ServerMessage[]) => {
    for (const m of rows) lastServerId.current = Math.max(lastServerId.current, m.id);
  };

  const loadWelcome = useCallback(async (lang: "en" | "am") => {
    const res = await api.get<APIResponse<{ reply: AssistantReply }>>(`/assistant/welcome?language=${lang}`);
    setMessages([{ id: nextId(), role: "assistant", reply: res.data.payload.reply }]);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const id = storedId(scope);
    (async () => {
      try {
        if (id) {
          const res = await api.get<APIResponse<ConversationPayload>>(`/assistant/conversations/${id}`);
          if (cancelled) return;
          const p = res.data.payload;
          conversationId.current = p.conversationId;
          setLanguage(p.language);
          setChannel(p.channel ?? "agent");
          setTicket(p.ticket ?? null);
          seen(p.messages);
          setMessages(p.messages.map(fromServer));
          if (p.messages.length) return;
        }
      } catch {
        storeId(scope, null);
      }
      if (!cancelled) await loadWelcome("en").catch(() => setError("The assistant is not reachable right now."));
    })();
    return () => {
      cancelled = true;
    };
  }, [scope, loadWelcome]);

  // While a person is handling the request, bring their replies in
  const ticketOpen = !!ticket && !CLOSED.has(ticket.status);
  useEffect(() => {
    if (!ticketOpen) return;
    const timer = setInterval(async () => {
      const id = conversationId.current;
      if (!id || document.hidden) return;
      try {
        const res = await api.get<APIResponse<ConversationPayload>>(
          `/assistant/conversations/${id}?after=${lastServerId.current}`,
        );
        const p = res.data.payload;
        // Our own turns are already on screen; only replies from staff are new
        const fresh = p.messages.filter((m) => m.role === "staff");
        seen(p.messages);
        if (fresh.length) {
          setMessages((list) => {
            const have = new Set(list.map((m) => m.id));
            return [...list, ...fresh.map(fromServer).filter((m) => !have.has(m.id))];
          });
        }
        if (p.channel) setChannel(p.channel);
        if (p.ticket !== undefined) setTicket(p.ticket);
      } catch {
        // The next tick tries again
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [ticketOpen]);

  const send = useCallback(
    async (input: { message?: string; action?: AssistantAction }) => {
      if (pending) return;
      const shown = input.message ?? (input.action ? actionLabel(input.action) : "");
      if (shown) setMessages((m) => [...m, { id: nextId(), role: "user", text: shown }]);
      setPending(true);
      setError(null);
      try {
        const res = await api.post<APIResponse<TurnResult>>("/assistant/turn", {
          conversation_id: conversationId.current,
          message: input.message,
          action: input.action,
          context_service: options.contextService ?? undefined,
        });
        const result = res.data.payload;
        conversationId.current = result.conversationId;
        storeId(scope, result.conversationId);
        setLanguage(result.language);
        if (result.channel) setChannel(result.channel);
        if (result.ticket !== undefined) setTicket(result.ticket ?? null);
        const reply = result.reply;
        if (reply) setMessages((m) => [...m, { id: nextId(), role: "assistant", reply }]);
        onTurn.current?.(result);
      } catch (err) {
        setError(getErrorMessage(err, "Something went wrong. Please try again."));
      } finally {
        setPending(false);
      }
    },
    [pending, scope, options.contextService],
  );

  const startOver = useCallback(async () => {
    conversationId.current = null;
    lastServerId.current = 0;
    storeId(scope, null);
    setError(null);
    setChannel("agent");
    setTicket(null);
    await loadWelcome(language).catch(() => setError("The assistant is not reachable right now."));
  }, [scope, language, loadWelcome]);

  const switchLanguage = useCallback(
    (lang: "en" | "am") => {
      setLanguage(lang);
      if (conversationId.current) void send({ action: { type: "language", value: lang } });
      else void loadWelcome(lang);
    },
    [send, loadWelcome],
  );

  const getConversationId = useCallback(() => conversationId.current, []);

  return {
    messages,
    language,
    pending,
    error,
    channel,
    ticket,
    getConversationId,
    send,
    startOver,
    switchLanguage,
  };
}

export type AssistantController = ReturnType<typeof useAssistant>;
