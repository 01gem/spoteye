import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // The FastAPI backend (Milestone 5A); the app only ever fetches relative /api URLs.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // If the backend dies mid-stream (uvicorn --reload kills it on Windows), close the
        // browser's connection too; otherwise the SSE stream hangs and EventSource never reconnects.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, _req, res) => {
            proxyRes.on('close', () => {
              if (!res.writableEnded) res.destroy()
            })
          })
        },
      },
    },
  },
})
