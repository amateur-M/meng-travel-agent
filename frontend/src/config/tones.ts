/**
 * Semantic tone tokens (V6/T1.4).
 *
 * Every place that used to reach for a raw Tailwind hue — `bg-sky-50`,
 * `text-amber-800`, `border-rose-200` — now asks for a *role* instead. The roles
 * map to CSS variables (see tailwind.config.ts `tone.*`), which index.css
 * re-assigns for dark mode. That is the whole fix: a categorical colour is a
 * decision, not a value, and the decision lives in exactly one place.
 *
 * Why not just add `dark:` variants inline? Because there are 48 call sites; 48
 * paired class strings drift out of sync the first time someone edits one half.
 * A token cannot drift.
 *
 * Every class here is a *literal* string so Tailwind's scanner can see it.
 * Constructing them at runtime (`"bg-" + hue`) yields classes that never get
 * generated — the styles silently do nothing.
 */

/** A hue with four roles: panel, text on it, its border, and a solid fill. */
export type Tone = "sky" | "violet" | "indigo" | "emerald" | "amber" | "orange" | "rose";

export interface ToneClasses {
  /** Tinted panel background. */
  soft: string;
  /** Text/icon readable on that panel, and as a standalone accent. */
  strong: string;
  /** Border matching the panel. */
  line: string;
  /** Solid fill for progress bars and small badges (pairs with white text). */
  fill: string;
  /** Chip: panel + text + border together. */
  chip: string;
  /** Container: panel + border, children carry their own colours. */
  panel: string;
}

export const TONE: Record<Tone, ToneClasses> = {
  sky: {
    soft: "bg-tone-sky-soft",
    strong: "text-tone-sky-strong",
    line: "border-tone-sky-line",
    fill: "bg-tone-sky-strong",
    chip: "bg-tone-sky-soft text-tone-sky-strong border-tone-sky-line",
    panel: "bg-tone-sky-soft border-tone-sky-line",
  },
  violet: {
    soft: "bg-tone-violet-soft",
    strong: "text-tone-violet-strong",
    line: "border-tone-violet-line",
    fill: "bg-tone-violet-strong",
    chip: "bg-tone-violet-soft text-tone-violet-strong border-tone-violet-line",
    panel: "bg-tone-violet-soft border-tone-violet-line",
  },
  indigo: {
    soft: "bg-tone-indigo-soft",
    strong: "text-tone-indigo-strong",
    line: "border-tone-indigo-line",
    fill: "bg-tone-indigo-strong",
    chip: "bg-tone-indigo-soft text-tone-indigo-strong border-tone-indigo-line",
    panel: "bg-tone-indigo-soft border-tone-indigo-line",
  },
  emerald: {
    soft: "bg-tone-emerald-soft",
    strong: "text-tone-emerald-strong",
    line: "border-tone-emerald-line",
    fill: "bg-tone-emerald-strong",
    chip: "bg-tone-emerald-soft text-tone-emerald-strong border-tone-emerald-line",
    panel: "bg-tone-emerald-soft border-tone-emerald-line",
  },
  amber: {
    soft: "bg-tone-amber-soft",
    strong: "text-tone-amber-strong",
    line: "border-tone-amber-line",
    fill: "bg-tone-amber-strong",
    chip: "bg-tone-amber-soft text-tone-amber-strong border-tone-amber-line",
    panel: "bg-tone-amber-soft border-tone-amber-line",
  },
  orange: {
    soft: "bg-tone-orange-soft",
    strong: "text-tone-orange-strong",
    line: "border-tone-orange-line",
    fill: "bg-tone-orange-strong",
    chip: "bg-tone-orange-soft text-tone-orange-strong border-tone-orange-line",
    panel: "bg-tone-orange-soft border-tone-orange-line",
  },
  rose: {
    soft: "bg-tone-rose-soft",
    strong: "text-tone-rose-strong",
    line: "border-tone-rose-line",
    fill: "bg-tone-rose-strong",
    chip: "bg-tone-rose-soft text-tone-rose-strong border-tone-rose-line",
    panel: "bg-tone-rose-soft border-tone-rose-line",
  },
};

/** Two-tone gradients for placeholder illustrations (literal class strings). */
export const TONE_GRADIENT: Record<Tone, string> = {
  sky: "from-tone-sky-soft to-tone-indigo-soft",
  violet: "from-tone-violet-soft to-tone-rose-soft",
  indigo: "from-tone-indigo-soft to-tone-sky-soft",
  emerald: "from-tone-emerald-soft to-tone-sky-soft",
  amber: "from-tone-amber-soft to-tone-orange-soft",
  orange: "from-tone-orange-soft to-tone-amber-soft",
  rose: "from-tone-rose-soft to-tone-violet-soft",
};
