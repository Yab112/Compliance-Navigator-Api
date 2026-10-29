"use client";

import { AxiosError } from "axios";
import useMutationFunc from "@cn/core/hooks/use-mutation";
import { MTD } from "@cn/core/lib/constants/methods";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import type { APIResponse } from "@cn/core/types/global";
import type { ChatRequest, ChatResponse } from "@/types/chat";

export class ChatApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ChatApiError";
  }
}

export const useSendMessage = () => {
  const { mutateAsync, isPending } = useMutationFunc<
    APIResponse<ChatResponse>,
    ChatRequest
  >();

  const sendMessage = async (input: ChatRequest): Promise<ChatResponse> => {
    try {
      const data = await mutateAsync({
        url: apiPaths.chat,
        method: MTD.POST,
        body: input,
        headers: { "Content-Type": "application/json" },
      });
      return data.payload;
    } catch (err) {
      if (err instanceof AxiosError) {
        const msg =
          (err.response?.data as { detail?: string })?.detail ||
          (err.response?.data as { message?: string })?.message ||
          "Could not reach the chat service";
        throw new ChatApiError(msg, err.response?.status);
      }
      throw err;
    }
  };

  return { sendMessage, isSending: isPending };
};
