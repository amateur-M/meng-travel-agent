import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#fef2f2",
          100: "#ffe1e1",
          200: "#ffc8c8",
          300: "#ff9e9e",
          400: "#ff6b6b",
          500: "#ff4d4d",
          600: "#e63946",
          700: "#c1121f",
          800: "#a4161a",
          900: "#780000",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
