import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0", // for Docker
    port: 5173,
    allowedHosts: [".ngrok-free.app"],
    strictPort: true,
    watch: {
      usePolling: true,
    },
  },
});
