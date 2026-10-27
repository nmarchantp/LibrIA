import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import BookCover from './BookCover'
import './ProfileEditModal.css'
import './LibraryRemoveModal.css'

const focusable = 'button:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])'

export default function LibraryRemoveModal({ book, busy, error, onClose, onConfirm }) {
  const dialogRef = useRef(null)
  const cancelRef = useRef(null)
  const titleId = useId()
  const descriptionId = useId()
  const bookId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    const opener = document.activeElement
    const previousOverflow = document.body.style.overflow
    const previousGutter = document.documentElement.style.scrollbarGutter
    document.documentElement.style.scrollbarGutter = 'stable'
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    cancelRef.current.focus({ preventScroll: true })
    return () => {
      dialog.close()
      document.body.style.overflow = previousOverflow
      document.documentElement.style.scrollbarGutter = previousGutter
      if (opener?.isConnected) opener.focus({ preventScroll: true })
      else document.querySelector('.reader-library-manage-toggle')?.focus({ preventScroll: true })
    }
  }, [])

  useEffect(() => {
    if (busy) dialogRef.current.focus({ preventScroll: true })
  }, [busy])

  function trapFocus(event) {
    if (event.key !== 'Tab') return
    const targets = [...dialogRef.current.querySelectorAll(focusable)]
    const first = targets[0]
    const last = targets.at(-1)
    if (!first) { event.preventDefault(); dialogRef.current.focus(); return }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus()
    }
  }

  return createPortal(<dialog ref={dialogRef} tabIndex="-1" className="reader-profile-modal reader-remove-confirmation"
    aria-labelledby={titleId} aria-describedby={`${descriptionId} ${bookId}`}
    onKeyDown={trapFocus}
    onCancel={event => { event.preventDefault(); if (!busy) onClose() }}
    onClick={event => {
      const bounds = dialogRef.current.getBoundingClientRect()
      if (event.target === dialogRef.current &&
        (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) &&
        !busy) onClose()
    }}>
    <header className="reader-modal-heading">
      <div className="reader-modal-heading-copy"><h2 id={titleId}>¿Retirar de tu biblioteca?</h2></div>
      <button className="reader-modal-close" type="button" aria-label="Cancelar retiro" disabled={busy} onClick={onClose}><X size={21} aria-hidden="true" /></button>
    </header>
    <div className="reader-modal-fields reader-remove-fields">
      <div className="reader-remove-book-summary" id={bookId}>
        <BookCover book={book} />
        <div><h3>{book.title}</h3><p>{book.author || 'Autor no disponible'}</p></div>
      </div>
      <p id={descriptionId}>Este libro dejará de aparecer en tu biblioteca. Esta acción también puede afectar tus estadísticas y tu recorrido lector.</p>
      {error && <p className="reader-field-error" role="alert">{error}</p>}
      {busy && <p role="status">Retirando libro…</p>}
    </div>
    <footer className="reader-modal-footer">
      <button ref={cancelRef} type="button" disabled={busy} onClick={onClose}>Cancelar</button>
      <button className="reader-remove-confirm-button" type="button" disabled={busy} onClick={onConfirm}>{busy ? 'Retirando…' : 'Retirar libro'}</button>
    </footer>
  </dialog>, document.body)
}
