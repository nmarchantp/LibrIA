import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Configuración del servidor y del proceso de construcción de Vite.
export default defineConfig({
  // Habilita la transformación de JSX y la recarga rápida de componentes React.
  plugins: [react()],
  server: {
    // Expone el servidor fuera de localhost; es necesario al ejecutarlo en Docker.
    host: true,
    // Puerto único acordado para el frontend durante el desarrollo.
    port: 5173,
    // Si 5173 está ocupado, muestra un error en vez de elegir otro puerto ocultamente.
    strictPort: true,
  },
})
