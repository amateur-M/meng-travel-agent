import { create } from "zustand";
import type { Theme } from "../types/trip";

/** What the user picked. `system` defers to the OS and follows it live. */
export type ThemePreference = Theme | "system";

const KEY_THEME = "coupletrip.theme";

function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(KEY_THEME);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // storage disabled — fall through to the OS preference
  }
  return "system";
}

function systemTheme(): Theme {
  if (typeof window === "undefined" || !window.matchMedia) {
    return "light";
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function resolveTheme(preference: ThemePreference): Theme {
  return preference === "system" ? systemTheme() : preference;
}

function writePreference(preference: ThemePreference): void {
  try {
    localStorage.setItem(KEY_THEME, preference);
  } catch {
    // storage disabled — the choice simply will not survive a reload
  }
}

interface UIStore {
  /** The concrete theme currently painted. */
  theme: Theme;
  /** The user's choice; `system` means "follow the OS". */
  preference: ThemePreference;
  reducedMotion: boolean;
  setTheme: (theme: Theme) => void;
  /** Cycles light → dark → system, which is the only way to get back to auto. */
  cycleTheme: () => void;
  toggleReducedMotion: () => void;
}

/**
 * Theme state (V6/T1).
 *
 * Was: `theme` hardcoded to "light", no persistence, no OS detection — so a
 * reload forgot the choice and a user on a dark desktop got a white flash. Now
 * the preference is persisted, `system` follows `prefers-color-scheme` live, and
 * index.html applies the resolved value *before first paint* so there is no
 * flash (the store then just syncs to what is already on the document).
 */
export const useUIStore = create<UIStore>((set, get) => ({
  theme: resolveTheme(readPreference()),
  preference: readPreference(),
  reducedMotion: false,

  setTheme: (theme) => {
    // A concrete pick means the user is overriding the OS.
    writePreference(theme);
    set({ theme, preference: theme });
  },

  cycleTheme: () => {
    const current = get().preference;
    const next: ThemePreference =
      current === "light" ? "dark" : current === "dark" ? "system" : "light";
    writePreference(next);
    set({ preference: next, theme: resolveTheme(next) });
  },

  toggleReducedMotion: () =>
    set((state) => ({ reducedMotion: !state.reducedMotion })),
}));

/** Keep `system` honest: follow the OS while the preference is "system". */
export function watchSystemTheme(): () => void {
  if (typeof window === "undefined" || !window.matchMedia) {
    return () => {};
  }
  const query = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => {
    const { preference } = useUIStore.getState();
    if (preference === "system") {
      useUIStore.setState({ theme: systemTheme() });
    }
  };
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

export { KEY_THEME };
