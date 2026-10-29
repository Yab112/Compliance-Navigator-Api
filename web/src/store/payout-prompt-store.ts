import { create } from "zustand";

/** The "add your bank account" dialog: opened once per session on sign-in, or from a job card. */
type PayoutPromptStore = {
  open: boolean;
  show: () => void;
  hide: () => void;
};

export const usePayoutPromptStore = create<PayoutPromptStore>((set) => ({
  open: false,
  show: () => set({ open: true }),
  hide: () => set({ open: false }),
}));
