import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // /cli serves this app and exposes the local findings/attack-event feed
      // under /api during dev too — point this at wherever the agent is running.
      '/api': process.env.VITE_AGENT_URL || 'http://localhost:8765',
    },
  },
})
