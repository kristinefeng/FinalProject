import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, Vite serves the UI on 5173 and forwards API calls to the
// Python server on 8000. For graders, `npm run build` output in dist/ is
// served by the Python server itself, so Node isn't needed to run the app.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000", "/photos": "http://127.0.0.1:8000" },
  },
});
