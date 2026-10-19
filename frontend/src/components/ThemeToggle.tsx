import { Moon, Sun } from "lucide-react";
import { useUIStore } from "../stores/uiStore";

/**
 * The dark-mode switch (V4/T2.6).
 *
 * The theme was already wired through uiStore → `document.documentElement.dataset.theme`
 * → the CSS variables in index.css, but nothing in the UI ever called `setTheme`,
 * so the dark palette was unreachable. This button lives in the shared header and
 * flips between the two themes.
 */
export function ThemeToggle() {
  const theme = useUIStore((state) => state.theme);
  const setTheme = useUIStore((state) => state.setTheme);
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "切换到浅色模式" : "切换到深色模式"}
      title={isDark ? "浅色模式" : "深色模式"}
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-cream-200 bg-surface text-ink-500 transition hover:text-ink-900"
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
