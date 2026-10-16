import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 用 127.0.0.1 而非 localhost：Node 18+ 会把 localhost 解析为 IPv6 ::1，
      // 而后端 uvicorn 默认只监听 IPv4，导致 ECONNREFUSED
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
