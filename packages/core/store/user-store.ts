import { create } from "zustand";
import type { AuthStatus, User } from "../types/user-types";

type UserStore = {
  user: User | null;
  status: AuthStatus;
  /** Kept in memory only, the refresh token lives in an httpOnly cookie. */
  accessToken: string | null;
  setUser: (user: User | null) => void;
  setSession: (user: User, accessToken: string) => void;
  clearSession: () => void;
};

export const useUserStore = create<UserStore>((set) => ({
  user: null,
  status: "loading",
  accessToken: null,
  setUser: (user) => set({ user }),
  setSession: (user, accessToken) => set({ user, accessToken, status: "authenticated" }),
  clearSession: () => set({ user: null, accessToken: null, status: "anonymous" }),
}));
