export const magicalBackgroundStorageKey = 'libriaverse-magical-background'
export const magicalBackgroundMotionStorageKey = 'libriaverse-magical-background-motion'

export function readMagicalBackground() {
  try { return localStorage.getItem(magicalBackgroundStorageKey) !== 'false' }
  catch { return true }
}

export function readMagicalBackgroundMotion() {
  try { return localStorage.getItem(magicalBackgroundMotionStorageKey) !== 'false' }
  catch { return true }
}
