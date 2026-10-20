import { createContext, useContext, useEffect, useState } from 'react'
import { applyTheme, readTheme, themeStorageKey, validTheme } from '../theme/themes'

const ThemeContext = createContext(null)

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(readTheme)
  useEffect(() => {
    applyTheme(theme)
    try { localStorage.setItem(themeStorageKey, theme) } catch { /* Storage may be disabled. */ }
  }, [theme])
  useEffect(() => {
    const sync = event => {
      if (event.key === themeStorageKey || event.key === null) setTheme(readTheme())
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  function selectTheme(id) {
    if (validTheme(id)) { applyTheme(id); setTheme(id) }
  }
  return <ThemeContext.Provider value={{ theme, selectTheme }}>{children}</ThemeContext.Provider>
}

// Match the existing context/hook pattern used by AuthContext and LibraryContext.
// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() { return useContext(ThemeContext) }
