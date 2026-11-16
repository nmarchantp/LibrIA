import { readTheme } from './themes'

export const magicalBackgroundStorageKey = 'libriaverse-magical-background'
export const magicalBackgroundMotionStorageKey = 'libriaverse-magical-background-motion'

export function readMagicalBackground() {
  try { return localStorage.getItem(magicalBackgroundStorageKey) !== 'false' }
  catch { return true }
}

export function readMagicalBackgroundMotion() {
  const defaultMotion = !['dark', 'lavanda'].includes(readTheme())
  try {
    const saved = localStorage.getItem(magicalBackgroundMotionStorageKey)
    return saved === null ? defaultMotion : saved !== 'false'
  } catch { return defaultMotion }
}
