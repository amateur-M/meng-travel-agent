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
      boxShadow: {
        soft: "0 16px 40px rgba(78, 47, 55, 0.08)",
        lift: "0 20px 50px rgba(78, 47, 55, 0.12)",
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
      },
      animation: {
        float: "float 5s ease-in-out infinite",
        "float-delayed": "float 5s ease-in-out 1.2s infinite",
        "pulse-soft": "pulse-soft 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
