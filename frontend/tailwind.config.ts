import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: {
          50: "#fffaf4",
          100: "#fff5e9",
          200: "#f9e8d5",
          300: "#f2d4b7",
        },
        blush: {
          50: "#fff5f7",
          100: "#ffe3ea",
          200: "#f9c2d1",
          300: "#f399b2",
          400: "#e76c8d",
          500: "#cc456d",
          600: "#a93255",
          700: "#832841",
        },
        gold: {
          100: "#faf0d7",
          200: "#efd79e",
          300: "#ddb866",
          400: "#c7943c",
          500: "#a9742d",
          600: "#825522",
        },
        ink: {
          900: "#30252a",
          700: "#57474d",
          500: "#79666c",
          400: "#9a858b",
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
