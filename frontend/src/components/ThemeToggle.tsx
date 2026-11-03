import { Monitor, Moon, Sun } from "lucide-react";
import { useUIStore, type ThemePreference } from "../stores/uiStore";

const LABEL: Record<ThemePreference, string> = {
  light: "浅色模式（点击：深色）",
  dark: "深色模式（点击：跟随系统）",
  system: "跟随系统（点击：浅色）",
};

/**
 * The dark-mode switch (V4/T2.6, reworked in V6/T1.1).
 *
 * V4 fixed the "theme is wired but unreachable" bug by adding this button, but a
 * two-state toggle forces a permanent override: once you tap it, the app can
 * never follow the OS again without clearing storage. It now cycles
 * light → dark → system, so "follow the system" stays reachable, and the icon
 * shows which state you are actually in rather than only the current paint.
 */
export function ThemeToggle() {
  const preference = useUIStore((state) => state.preference);
  const cycleTheme = useUIStore((state) => state.cycleTheme);

  const Icon =
    preference === "system" ? Monitor : preference === "dark" ? Sun : Moon;

  return (
    <button
      type="button"
      onClick={cycleTheme}
      aria-label={LABEL[preference]}
      title={LABEL[preference]}
      className="ct-btn-icon"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}
