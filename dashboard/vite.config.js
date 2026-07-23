import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Documentation.jsx does a `?raw` import of the repo root's README.md,
    // which lives outside /dashboard (vite's default server root) — allow it.
    fs: {
      allow: ['..'],
    },
    proxy: {
      // /cli serves this app and exposes the local findings/attack-event feed
      // under /api during dev too — point this at wherever the agent is running.
      '/api': process.env.VITE_AGENT_URL || 'http://localhost:8765',
      '/ws': {
        target: (process.env.VITE_AGENT_URL || 'http://localhost:8765').replace('http', 'ws'),
        ws: true,
      },
    },
  },
})
