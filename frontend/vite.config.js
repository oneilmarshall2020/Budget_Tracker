import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The page calls the backend at /api/... on its own address. Vite passes those
    // calls on to FastAPI (dropping the /api), so to the browser it's all one site.
    // That's what lets the login cookie work. Once deployed, the host does the same.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
