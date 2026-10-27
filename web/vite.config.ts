import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1200 }, // ECharts dominates; one chunk is fine here
  server: {
    port: 5173,
    // In dev, proxy API calls so no CORS setup is needed.
    proxy: { "/api": process.env.VITE_DEV_API ?? "http://localhost:8000" },
  },
  test: {
    // Frontend tests live in ../AiMix/web_tests (removable before submission).
    root: path.resolve(import.meta.dirname, ".."),
    include: ["AiMix/web_tests/**/*.test.ts"],
    globals: true,
    environment: "node",
    passWithNoTests: true,
  },
});
