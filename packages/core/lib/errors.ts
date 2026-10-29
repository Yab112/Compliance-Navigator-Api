import { AxiosError } from "axios";

/** Human-readable message from an API error (FastAPI sends `detail`). */
export function getErrorMessage(error: unknown, fallback = "Something went wrong"): string {
  if (error instanceof AxiosError) {
    if (error.code === "ERR_NETWORK") return "Can't reach the server. Check your connection.";
    const data = error.response?.data as { detail?: unknown; message?: string } | undefined;
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      const first = data.detail[0] as { msg?: string; loc?: string[] } | undefined;
      if (first?.msg) return `${first.loc?.slice(-1)[0] ?? "Field"}: ${first.msg}`;
    }
    return data?.message ?? fallback;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}
