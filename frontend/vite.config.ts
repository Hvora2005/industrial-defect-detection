import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const backend = process.env.ACERO_BACKEND_URL || "http://127.0.0.1:8000";
const routes = [
  "/health",
  "/runtime",
  "/cameras",
  "/camera",
  "/detect",
  "/preview",
  "/upload",
  "/history",
  "/stats",
  "/trend",
  "/captures",
  "/export",
];
export default defineConfig({
  plugins: [react()],
  base: "/static/",
  server: {
    proxy: Object.fromEntries([
      ...routes.map((route) => [route, { target: backend }]),
      ["/ws", { target: backend, ws: true }],
    ]),
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    restoreMocks: true,
  },
});
