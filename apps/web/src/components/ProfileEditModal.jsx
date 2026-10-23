import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import './ProfilePreferences.css'
import './ProfileEditModal.css'

const focusable = 'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])'

function EditDialog({ title, icon, description, dirty, busy, saveDisabled, onClose, onSubmit, children }) {
  const dialogRef = useRef(null)
  const continueRef = useRef(null)
  const previousField = useRef(null)
  const [confirming, setConfirming] = useState(false)
  const titleId = useId()
  const descriptionId = useId()
  useEffect(() => {
    const dialog = dialogRef.current
    const opener = document.activeElement
    const previousOverflow = document.body.style.overflow
    const previousGutter = document.documentElement.style.scrollbarGutter
    // Reserve the existing scrollbar space so opening a dialog never resizes cards.
    document.documentElement.style.scrollbarGutter = 'stable'
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    const firstField = dialog.querySelector('textarea:not(:disabled), input:not(:disabled), select:not(:disabled)')
    ;(firstField || dialog.querySelector('button')).focus({ preventScroll: true })
    // Disabled fields may temporarily leave focus on the document during a save.
    // Intercept Escape before the browser's native close watcher in that case too.
    const escape = event => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopPropagation()
      dialog.dispatchEvent(new Event('cancel', { cancelable: true }))
    }
    document.addEventListener('keydown', escape, true)
    return () => {
      document.removeEventListener('keydown', escape, true)
      dialog.close()
      document.body.style.overflow = previousOverflow
      document.documentElement.style.scrollbarGutter = previousGutter
      if (opener?.isConnected) opener.focus({ preventScroll: true })
    }
  }, [])
  // Catalog loading can temporarily unmount the focused selector. Re-home focus
  // after content updates as well as when all fields become disabled for saving.
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog.contains(document.activeElement)) {
      const target = [...dialog.querySelectorAll(focusable)].find(element => element.getClientRects().length && !element.closest('[hidden]'))
      ;(target || dialog).focus({ preventScroll: true })
    }
  })
  useEffect(() => {
    if (confirming) continueRef.current?.focus()
    else if (previousField.current?.isConnected) {
      previousField.current.focus({ preventScroll: true })
      previousField.current = null
    }
  }, [confirming])
  function requestClose() {
    if (busy) return
    if (dirty) {
      previousField.current = document.activeElement
      setConfirming(true)
    } else onClose()
  }
  function trapFocus(event) {
    if (event.key !== 'Tab') return
    const targets = [...dialogRef.current.querySelectorAll(focusable)].filter(element => element.getClientRects().length && !element.closest('[hidden]'))
    const first = targets[0]
    const last = targets.at(-1)
    if (!first) { event.preventDefault(); dialogRef.current.focus(); return }
    if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) {
      event.preventDefault(); last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus()
    }
  }
  return <dialog ref={dialogRef} className="reader-profile-modal" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}
    onKeyDown={trapFocus}
    onCancel={event => { event.preventDefault(); if (confirming) setConfirming(false); else requestClose() }}
    onClick={event => {
      const bounds = dialogRef.current.getBoundingClientRect()
      if (event.target === dialogRef.current && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) {
        if (confirming) return
        requestClose()
      }
    }}>
    <header className="reader-modal-heading">
      <div className="reader-modal-heading-copy"><h2 id={titleId}>{icon}{confirming ? '¿Descartar cambios?' : title}</h2><p id={descriptionId}>{confirming ? 'Tienes cambios sin guardar. Si cierras el editor, se perderán.' : description}</p></div>
      <button className="reader-modal-close" type="button" disabled={busy} aria-label={confirming ? 'Volver al editor' : 'Cerrar editor'} onClick={() => { if (confirming) setConfirming(false); else requestClose() }}><X size={21} aria-hidden="true" /></button>
    </header>
    {confirming && <div className="reader-modal-discard" role="alert"><p>Tu información guardada se conservará.</p><div className="reader-modal-footer"><button ref={continueRef} type="button" onClick={() => setConfirming(false)}>Seguir editando</button><button className="reader-discard-button" type="button" onClick={onClose}>Descartar cambios</button></div></div>}
    <form className="reader-preferences-form reader-modal-form" onSubmit={onSubmit} aria-busy={busy} hidden={confirming}>
      <div className="reader-modal-fields">{children}</div>
      <footer className="reader-modal-footer"><button type="button" disabled={busy} onClick={requestClose}>Cancelar</button><button type="submit" disabled={busy || saveDisabled}>{busy ? 'Guardando…' : 'Guardar'}</button></footer>
    </form>
  </dialog>
}

export default function ProfileEditModal({ open, ...props }) {
  return open ? createPortal(<EditDialog {...props} />, document.body) : null
}
