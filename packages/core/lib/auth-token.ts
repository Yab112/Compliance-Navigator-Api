import { useUserStore } from "../store/user-store";

/** Current in-memory access token (never persisted to storage). */
export function getAccessToken(): string | null {
  return useUserStore.getState().accessToken;
}
