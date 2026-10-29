import { useEffect, useId } from 'react'

export function useUnsavedSessionWarning(dirty) {
  const id = useId()
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('libria:unsaved-changes', { detail: { id, dirty: Boolean(dirty) } }))
    const beforeUnload = event => {
      if (!dirty) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', beforeUnload)
    return () => {
      window.removeEventListener('beforeunload', beforeUnload)
      window.dispatchEvent(new CustomEvent('libria:unsaved-changes', { detail: { id, dirty: false } }))
    }
  }, [dirty, id])
}
