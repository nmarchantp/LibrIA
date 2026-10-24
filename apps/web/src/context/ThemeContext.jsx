import { createContext, useContext, useEffect, useState } from 'react'
import { applyTheme, readTheme, themeStorageKey, validTheme } from '../theme/themes'
import { magicalBackgroundStorageKey, readMagicalBackground } from '../theme/visualPreferences'

const ThemeContext = createContext(null)

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(readTheme)
  const [magicalBackground, setMagicalBackground] = useState(readMagicalBackground)
  useEffect(() => {
    try { localStorage.setItem(magicalBackgroundStorageKey, String(magicalBackground)) } catch { /* Storage may be disabled. */ }
  }, [magicalBackground])
  useEffect(() => {
    applyTheme(theme)
    try { localStorage.setItem(themeStorageKey, theme) } catch { /* Storage may be disabled. */ }
  }, [theme])
  useEffect(() => {
    const sync = event => {
      if (event.key === themeStorageKey || event.key === null) setTheme(readTheme())
      if (event.key === magicalBackgroundStorageKey || event.key === null) setMagicalBackground(readMagicalBackground())
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  function selectTheme(id) {
    if (validTheme(id)) { applyTheme(id); setTheme(id) }
  }
  return <ThemeContext.Provider value={{ theme, selectTheme, magicalBackground, setMagicalBackground }}>{children}</ThemeContext.Provider>
}

// Match the existing context/hook pattern used by AuthContext and LibraryContext.
// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() { return useContext(ThemeContext) }
