import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build is served by scripts/demo/sala_control.py under /static/; dev proxies the API to the Python server.
export default defineConfig({
  plugins: [react()],
  base: "/static/",
  build: { outDir: "../static", emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8765" } },
  test: { environment: "jsdom" },
});
