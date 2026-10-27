export const magicalBackgroundStorageKey = 'libriaverse-magical-background'

export function readMagicalBackground() {
  try { return localStorage.getItem(magicalBackgroundStorageKey) !== 'false' }
  catch { return true }
}
