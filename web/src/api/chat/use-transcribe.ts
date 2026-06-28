"use client";

import { AxiosError } from "axios";
import { api } from "@/lib/api";
import { apiPaths } from "@/lib/constants/api-paths";
import type { APIResponse } from "@/types/global";
import type { TranscribeResponse } from "@/types/chat";

export class TranscribeError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "TranscribeError";
  }
}

export async function transcribeAudio(blob: Blob): Promise<TranscribeResponse> {
  const form = new FormData();
  form.append("file", blob, "recording.webm");

  try {
    const { data } = await api.post<APIResponse<TranscribeResponse>>(
      apiPaths.chatTranscribe,
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return data.payload;
  } catch (err) {
    if (err instanceof AxiosError) {
      const msg =
        (err.response?.data as { detail?: string })?.detail ||
        "Could not transcribe audio";
      throw new TranscribeError(msg, err.response?.status);
    }
    throw err;
  }
}
