import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // V4/T2.5: every shade below resolves through a CSS variable that
        // index.css re-assigns under [data-theme="dark"], so the same class
        // (bg-cream-50, text-ink-900, ...) paints the right value per theme.
        // Cards/sheets use `surface` (was a hardcoded bg-white).
        surface: "rgb(var(--surface) / <alpha-value>)",
        cream: {
          50: "rgb(var(--cream-50) / <alpha-value>)",
          100: "rgb(var(--cream-100) / <alpha-value>)",
          200: "rgb(var(--cream-200) / <alpha-value>)",
          300: "rgb(var(--cream-300) / <alpha-value>)",
        },
        blush: {
          50: "rgb(var(--blush-50) / <alpha-value>)",
          100: "rgb(var(--blush-100) / <alpha-value>)",
          200: "rgb(var(--blush-200) / <alpha-value>)",
          300: "rgb(var(--blush-300) / <alpha-value>)",
          400: "rgb(var(--blush-400) / <alpha-value>)",
          500: "rgb(var(--blush-500) / <alpha-value>)",
          600: "rgb(var(--blush-600) / <alpha-value>)",
          700: "rgb(var(--blush-700) / <alpha-value>)",
        },
        gold: {
          50: "rgb(var(--gold-50) / <alpha-value>)",
          100: "rgb(var(--gold-100) / <alpha-value>)",
          200: "rgb(var(--gold-200) / <alpha-value>)",
          300: "rgb(var(--gold-300) / <alpha-value>)",
          400: "rgb(var(--gold-400) / <alpha-value>)",
          500: "rgb(var(--gold-500) / <alpha-value>)",
          600: "rgb(var(--gold-600) / <alpha-value>)",
        },
        ink: {
          300: "rgb(var(--ink-300) / <alpha-value>)",
          400: "rgb(var(--ink-400) / <alpha-value>)",
          500: "rgb(var(--ink-500) / <alpha-value>)",
          600: "rgb(var(--ink-600) / <alpha-value>)",
          700: "rgb(var(--ink-700) / <alpha-value>)",
          800: "rgb(var(--ink-800) / <alpha-value>)",
          900: "rgb(var(--ink-900) / <alpha-value>)",
        },
        // Solid CTA fill (primary buttons, logo badge, user bubble). Fixed —
        // it does NOT flip with the theme, because it always carries white
        // label text and must keep that contrast in light and dark alike. The
        // theme-flipping `blush` scale above is for tints, borders and accent
        // text/icons only.
        brand: {
          DEFAULT: "#cc456d",
          dark: "#a93255",
        },
        // V6/T0.1: the categorical palette. Activity types, weather kinds and
        // status messages each used to reach for a raw Tailwind hue (bg-sky-50,
        // text-amber-800, bg-rose-50...). Those bypass the theme entirely, so in
        // dark mode they painted pale pastel blocks on a dark page. Each hue now
        // exposes exactly three roles, and each role is a CSS variable that
        // index.css re-assigns for dark:
        //   soft   — tinted panel/surface behind content
        //   strong — text and icons on that panel
        //   line   — border/divider matching the panel
        // Hues are chosen by *meaning*, not decoration: emerald=success,
        // amber=warning, rose=danger, sky=info, the rest are activity kinds.
        tone: {
          sky: {
            soft: "rgb(var(--tone-sky-soft) / <alpha-value>)",
            strong: "rgb(var(--tone-sky-strong) / <alpha-value>)",
            line: "rgb(var(--tone-sky-line) / <alpha-value>)",
          },
          violet: {
            soft: "rgb(var(--tone-violet-soft) / <alpha-value>)",
            strong: "rgb(var(--tone-violet-strong) / <alpha-value>)",
            line: "rgb(var(--tone-violet-line) / <alpha-value>)",
          },
          indigo: {
            soft: "rgb(var(--tone-indigo-soft) / <alpha-value>)",
            strong: "rgb(var(--tone-indigo-strong) / <alpha-value>)",
            line: "rgb(var(--tone-indigo-line) / <alpha-value>)",
          },
          emerald: {
            soft: "rgb(var(--tone-emerald-soft) / <alpha-value>)",
            strong: "rgb(var(--tone-emerald-strong) / <alpha-value>)",
            line: "rgb(var(--tone-emerald-line) / <alpha-value>)",
          },
          amber: {
            soft: "rgb(var(--tone-amber-soft) / <alpha-value>)",
            strong: "rgb(var(--tone-amber-strong) / <alpha-value>)",
            line: "rgb(var(--tone-amber-line) / <alpha-value>)",
          },
          orange: {
            soft: "rgb(var(--tone-orange-soft) / <alpha-value>)",
            strong: "rgb(var(--tone-orange-strong) / <alpha-value>)",
            line: "rgb(var(--tone-orange-line) / <alpha-value>)",
          },
          rose: {
            soft: "rgb(var(--tone-rose-soft) / <alpha-value>)",
            strong: "rgb(var(--tone-rose-strong) / <alpha-value>)",
            line: "rgb(var(--tone-rose-line) / <alpha-value>)",
          },
        },
      },
      fontFamily: {
        sans: [
          "Avenir Next",
          "PingFang SC",
          "Microsoft YaHei",
          "system-ui",
          "sans-serif",
        ],
        hand: [
          "Kaiti SC",
          "STKaiti",
          "KaiTi",
          "Brush Script MT",
          "cursive",
        ],
      },
      // V6/T0.2: shadows are theme-aware. A warm near-black shadow is right on
      // cream, but on a dark surface it just disappears — dark mode swaps in a
      // deeper, more opaque one so cards still lift off the page.
      boxShadow: {
        soft: "0 1px 2px rgb(var(--shadow) / 0.04), 0 12px 32px rgb(var(--shadow) / 0.07)",
        lift: "0 2px 6px rgb(var(--shadow) / 0.06), 0 22px 54px rgb(var(--shadow) / 0.12)",
        ring: "0 0 0 1px rgb(var(--cream-200))",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        float: "float 5s ease-in-out infinite",
        "float-delayed": "float 5s ease-in-out 1.2s infinite",
        "pulse-soft": "pulse-soft 2.4s ease-in-out infinite",
        shimmer: "shimmer 1.6s ease-in-out infinite",
        "fade-up": "fade-up 0.3s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
