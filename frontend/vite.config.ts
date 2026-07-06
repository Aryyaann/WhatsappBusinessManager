import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Durante desarrollo, el frontend corre en :5173 y el backend en
      // :8000 — este proxy evita problemas de CORS reenviando /api/* al
      // backend real sin tener que configurar cabeceras CORS todavía.
      '/api': 'http://localhost:8000',
    },
  },
})