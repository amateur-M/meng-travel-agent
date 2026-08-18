import { create } from "zustand";
import type { Theme } from "../types/trip";

interface UIStore {
  theme: Theme;
  reducedMotion: boolean;
  setTheme: (theme: Theme) => void;
  toggleReducedMotion: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  theme: "light",
  reducedMotion: false,
  setTheme: (theme) => set({ theme }),
  toggleReducedMotion: () =>
    set((state) => ({ reducedMotion: !state.reducedMotion })),
}));
