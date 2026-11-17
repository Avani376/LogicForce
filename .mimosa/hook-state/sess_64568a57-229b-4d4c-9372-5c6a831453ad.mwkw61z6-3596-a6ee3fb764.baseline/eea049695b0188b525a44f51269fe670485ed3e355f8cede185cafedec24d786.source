import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api to the FastAPI service so the UI and engine share one origin.
// Production: serve apps/web/dist behind the same origin as the API (docs/DEPLOYMENT.md).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
