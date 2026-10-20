import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { LibraryProvider } from './context/LibraryContext'
import { AuthProvider } from './context/AuthContext'
import './styles.css'
import './theme/themes.css'
import { ThemeProvider } from './context/ThemeContext'
import { applyTheme, readTheme } from './theme/themes'

applyTheme(readTheme())

// Busca el elemento <div id="root"> definido en index.html y monta allí React.
// StrictMode ayuda a detectar prácticas problemáticas durante el desarrollo.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    {/* BrowserRouter sincroniza las pantallas con la URL del navegador. */}
    <BrowserRouter>
      {/* LibraryProvider comparte los libros y sus estados entre todas las rutas. */}
      <ThemeProvider><AuthProvider><LibraryProvider><App /></LibraryProvider></AuthProvider></ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
