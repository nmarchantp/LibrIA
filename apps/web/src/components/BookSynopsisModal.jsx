import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import './ProfileEditModal.css'

export default function BookSynopsisModal({ title, children, onClose }) {
  const dialogRef = useRef(null)
  const titleId = useId()
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
    }
  }, [])
  return createPortal(<dialog ref={dialogRef} className="reader-profile-modal book-synopsis-modal" aria-modal="true" aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); onClose() }}
    onClick={event => {
      const r = dialogRef.current.getBoundingClientRect()
      if (event.target === dialogRef.current && (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)) onClose()
    }}>
    <header className="reader-modal-heading"><div className="reader-modal-heading-copy"><h2 id={titleId}>Entre las páginas</h2><p>{title}</p></div><button type="button" className="reader-modal-close" aria-label="Cerrar sinopsis" onClick={onClose}><X aria-hidden="true" size={21} /></button></header>
    <div className="book-synopsis-body" tabIndex={0}>{children}</div>
  </dialog>, document.body)
}
