import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Configuración del servidor y del proceso de construcción de Vite.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const backend = new URL(env.VITE_API_URL || 'http://127.0.0.1:8000/api', 'http://127.0.0.1:8000')
  if (backend.hostname === 'localhost') backend.hostname = '127.0.0.1'
  return {
  // Habilita la transformación de JSX y la recarga rápida de componentes React.
  plugins: [react()],
  server: {
    // Expone el servidor fuera de localhost; es necesario al ejecutarlo en Docker.
    host: true,
    // Puerto único acordado para el frontend durante el desarrollo.
    port: 5173,
    // Si 5173 está ocupado, muestra un error en vez de elegir otro puerto ocultamente.
    strictPort: true,
    proxy: {
      [backend.pathname.replace(/\/$/, '') || '/api']: {
        target: backend.origin,
        changeOrigin: true,
      },
    },
  },
  }
})
