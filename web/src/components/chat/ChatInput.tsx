"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Textarea } from "@cn/ui/textarea";
import { Button } from "@cn/ui/button";
import { Spinner } from "@cn/ui/spinner";
import { transcribeAudio, TranscribeError } from "@/api/chat/use-transcribe";
import { cn } from "@cn/core/lib/utils";

type ChatInputProps = {
  onSend: (message: string) => void;
  disabled?: boolean;
  enableVoice?: boolean;
};

export function ChatInput({ onSend, disabled, enableVoice }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isTranscribing) return;
    onSend(trimmed);
    setValue("");
    textareaRef.current?.focus();
  }, [value, disabled, isTranscribing, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const stopRecording = useCallback(async () => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return;

    setIsRecording(false);

    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      recorder.stop();
    });

    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    chunksRef.current = [];

    if (blob.size < 1000) {
      setVoiceError("Recording too short, try again.");
      return;
    }

    setIsTranscribing(true);
    setVoiceError(null);
    try {
      const result = await transcribeAudio(blob);
      if (result.text) {
        setValue((prev) => (prev ? `${prev} ${result.text}` : result.text));
      } else {
        setVoiceError("No speech detected.");
      }
    } catch (err) {
      setVoiceError(
        err instanceof TranscribeError ? err.message : "Transcription failed.",
      );
    } finally {
      setIsTranscribing(false);
      textareaRef.current?.focus();
    }
  }, []);

  const startRecording = useCallback(async () => {
    setVoiceError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      setVoiceError("Microphone access denied.");
    }
  }, []);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const busy = disabled || isTranscribing;

  return (
    <div className="border-border shrink-0 border-t p-3">
      {voiceError && (
        <p className="text-destructive mb-2 text-xs">{voiceError}</p>
      )}
      {isRecording && (
        <p className="text-primary mb-2 animate-pulse text-xs">Listening… tap mic to stop</p>
      )}
      {isTranscribing && (
        <p className="text-muted-foreground mb-2 flex items-center gap-2 text-xs">
          <Spinner className="size-3" /> Transcribing…
        </p>
      )}
      <div className="flex items-end gap-2">
        {enableVoice && (
          <Button
            type="button"
            variant={isRecording ? "destructive" : "outline"}
            size="icon"
            className="shrink-0 self-end"
            onClick={toggleRecording}
            disabled={busy && !isRecording}
            aria-label={isRecording ? "Stop recording" : "Start voice input"}
          >
            <MicIcon className={cn("size-4", isRecording && "animate-pulse")} />
          </Button>
        )}
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type in English or Amharic…"
          disabled={busy}
          className="min-h-10 resize-none"
          rows={1}
        />
        <Button
          onClick={handleSend}
          disabled={busy || !value.trim()}
          size="sm"
          className="shrink-0 self-end"
        >
          Send
        </Button>
      </div>
    </div>
  );
}

function MicIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}
