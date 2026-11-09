import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies the API to the backend; PVORG_PORT matches the backend's port.
const backend = `http://127.0.0.1:${process.env.PVORG_PORT ?? "8000"}`;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
    },
  },
});
