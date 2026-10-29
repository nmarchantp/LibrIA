import { createContext, useContext, useEffect, useState } from 'react'
import { applyTheme, readTheme, themeStorageKey, validTheme } from '../theme/themes'
import { magicalBackgroundStorageKey, magicalBackgroundMotionStorageKey, readMagicalBackground, readMagicalBackgroundMotion } from '../theme/visualPreferences'

const ThemeContext = createContext(null)

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(readTheme)
  const [magicalBackground, setMagicalBackground] = useState(readMagicalBackground)
  const [magicalBackgroundMotion, setMagicalBackgroundMotion] = useState(readMagicalBackgroundMotion)
  useEffect(() => {
    try { localStorage.setItem(magicalBackgroundStorageKey, String(magicalBackground)) } catch { /* Storage may be disabled. */ }
  }, [magicalBackground])
  useEffect(() => {
    try { localStorage.setItem(magicalBackgroundMotionStorageKey, String(magicalBackgroundMotion)) } catch { /* Storage may be disabled. */ }
  }, [magicalBackgroundMotion])
  useEffect(() => {
    applyTheme(theme)
    try { localStorage.setItem(themeStorageKey, theme) } catch { /* Storage may be disabled. */ }
  }, [theme])
  useEffect(() => {
    const sync = event => {
      if (event.key === themeStorageKey || event.key === null) setTheme(readTheme())
      if (event.key === magicalBackgroundStorageKey || event.key === null) setMagicalBackground(readMagicalBackground())
      if (event.key === magicalBackgroundMotionStorageKey || event.key === null) setMagicalBackgroundMotion(readMagicalBackgroundMotion())
    }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  function selectTheme(id) {
    if (validTheme(id)) { applyTheme(id); setTheme(id) }
  }
  return <ThemeContext.Provider value={{ theme, selectTheme, magicalBackground, setMagicalBackground, magicalBackgroundMotion, setMagicalBackgroundMotion }}>{children}</ThemeContext.Provider>
}

// Match the existing context/hook pattern used by AuthContext and LibraryContext.
// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() { return useContext(ThemeContext) }
