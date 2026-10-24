import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { BookOpen, ChevronRight, X } from 'lucide-react'
import BookCover from './BookCover'
import './ProfileEditModal.css'
import './LibraryManageModal.css'

export default function LibraryManageModal({ book, busy, error, onClose, onChangeStatus, onRemove }) {
  const dialogRef = useRef(null)
  const titleId = useId()
  const bookId = useId()
  useEffect(() => {
    const dialog = dialogRef.current
    const opener = document.activeElement
    const overflow = document.body.style.overflow
    const gutter = document.documentElement.style.scrollbarGutter
    document.documentElement.style.scrollbarGutter = 'stable'
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    dialog.querySelector('button').focus({ preventScroll: true })
    return () => {
      dialog.close()
      document.body.style.overflow = overflow
      document.documentElement.style.scrollbarGutter = gutter
      if (opener?.isConnected) opener.focus({ preventScroll: true })
      else document.querySelector('.reader-library-filters button.active')?.focus({ preventScroll: true })
    }
  }, [])

  return createPortal(<dialog ref={dialogRef} className="reader-profile-modal reader-library-modal" aria-labelledby={titleId} aria-describedby={bookId}
    onCancel={event => { event.preventDefault(); if (!busy) onClose() }}
    onKeyDown={event => {
      if (event.key !== 'Tab') return
      const targets = [...dialogRef.current.querySelectorAll('button:not(:disabled), a[href], select:not(:disabled)')]
      const first = targets[0]
      const last = targets.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }}>
    <header className="reader-modal-heading">
      <div className="reader-modal-heading-copy"><h2 id={titleId}>Gestionar libro</h2></div>
      <button className="reader-modal-close" type="button" aria-label="Cerrar gestión del libro" onClick={onClose} disabled={busy}><X size={21} aria-hidden="true" /></button>
    </header>
    <div className="reader-modal-fields" aria-busy={busy}>
      <div className="reader-library-book-summary" id={bookId}>
        <BookCover book={book} />
        <div className="reader-library-book-copy">
          <h3>{book.title}</h3><p>{book.author || 'Autor no disponible'}</p>
          <div className="reader-library-progress-action">
            <Link className="button primary" to={`/library/${encodeURIComponent(book.id)}`} aria-disabled={busy} onClick={event => { if (busy) event.preventDefault(); else onClose() }}><BookOpen size={20} aria-hidden="true" /><span>Ver ficha y registrar avance</span><ChevronRight size={19} aria-hidden="true" /></Link>
          </div>
        </div>
      </div>
      <p className="reader-library-help">Puedes abandonar un libro en “Registrar avance”; el motivo es opcional.</p>
      <label className="reader-library-state">Estado de lectura<select disabled={busy} value={book.status} aria-label={`Estado de ${book.title}`} onChange={event => onChangeStatus(book, event.target.value)}>
        <option>Leyendo</option><option disabled={book.status !== 'Pendiente'}>Pendiente</option><option disabled={!['Pendiente', 'Leyendo', 'Terminado'].includes(book.status)}>Terminado</option><option disabled>Abandonado</option>
      </select></label>
      {error && <p className="reader-field-error" role="alert">{error}</p>}
      {busy && <p role="status">Guardando cambios…</p>}
      <div className="reader-library-danger"><button className="reader-book-remove" type="button" disabled={busy} onClick={() => {
        if (window.confirm(`¿Retirar “${book.title}” de tu biblioteca? Se recalculará tu perfil sin esta experiencia.`)) onRemove(book)
      }}>Retirar de mi biblioteca</button><p className="reader-library-help">Al retirar un libro se recalcula tu perfil sin esa experiencia.</p></div>
    </div>
  </dialog>, document.body)
}
