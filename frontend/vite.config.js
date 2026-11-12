import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // En desarrollo local (npm run dev) /api se reenvía al nginx del docker compose.
    proxy: {
      '/api': 'http://localhost',
    },
  },
})
