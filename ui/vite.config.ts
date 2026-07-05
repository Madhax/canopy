import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The UI talks to the FastAPI server on :8700; Vite proxies /api during dev.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Ensure a single React instance across the workspace (avoids "Invalid hook call").
  resolve: { dedupe: ["react", "react-dom"] },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8700",
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
  },
});
