import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Windows host -> Docker Desktop bind mounts don't propagate native
    // filesystem change events into the Linux container, so chokidar's
    // default watch mode never sees host edits - polling is the standard
    // workaround.
    watch: {
      usePolling: true,
    },
  },
})
