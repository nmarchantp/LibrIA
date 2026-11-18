import { useEffect, useId, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { BookOpen, ChevronRight, Sparkles, X } from 'lucide-react'
import BookCover from './BookCover'
import RatingStar from './RatingStar'
import { parseBookSynopsis } from './bookSynopsis'
import './ProfileEditModal.css'
import './RecommendationPreview.css'

// normalizeGoogleBook fills this text in when Google Books has no description.
const placeholderDescription = 'Resultado obtenido desde Google Books.'

// Quick look at a recommended book: synopsis, details and Gemini's reason, without leaving the page.
export default function RecommendationPreview({ book, reason, genre, action, onClose }) {
  const dialogRef = useRef(null)
  const titleId = useId()
  const synopsis = useMemo(() => parseBookSynopsis(book.description === placeholderDescription ? '' : book.description), [book.description])
  const rating = Number(book.averageRating)
  const year = book.year || Number(String(book.publishedDate || '').slice(0, 4)) || null
  const details = [genre, year, book.pageCount > 0 ? `${book.pageCount} páginas` : null].filter(Boolean)

  useEffect(() => {
    const dialog = dialogRef.current
    const opener = document.activeElement
    const overflow = document.body.style.overflow
    const gutter = document.documentElement.style.scrollbarGutter
    document.documentElement.style.scrollbarGutter = 'stable'
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    dialog.querySelector('.reader-modal-close').focus({ preventScroll: true })
    return () => {
      dialog.close()
      document.body.style.overflow = overflow
      document.documentElement.style.scrollbarGutter = gutter
      if (opener?.isConnected) opener.focus({ preventScroll: true })
    }
  }, [])

  return createPortal(<dialog ref={dialogRef} className="reader-profile-modal recommendation-preview" aria-modal="true" aria-labelledby={titleId}
    onCancel={event => { event.preventDefault(); onClose() }}
    onClick={event => {
      const r = dialogRef.current.getBoundingClientRect()
      if (event.target === dialogRef.current && (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)) onClose()
    }}>
    <button type="button" className="reader-modal-close recommendation-preview-close" aria-label="Cerrar resumen" onClick={onClose}><X aria-hidden="true" size={20} /></button>
    <div className="recommendation-preview-body">
      <div className="recommendation-preview-cover"><BookCover book={book} /></div>
      <div className="recommendation-preview-copy">
        <h2 id={titleId}>{book.title}</h2>
        <p className="recommendation-preview-author">{book.author}</p>
        {(details.length > 0 || rating > 0) && <p className="recommendation-preview-details">
          {rating > 0 && <span className="recommendation-preview-rating" aria-label={`Valoración promedio ${rating.toFixed(1)}`}><RatingStar selected />{rating.toFixed(1)}</span>}
          {details.map(detail => <span key={detail}>{detail}</span>)}
        </p>}
        <section className="recommendation-preview-section" aria-label="Sinopsis">
          <h3><BookOpen aria-hidden="true" />Sinopsis</h3>
          <div className="recommendation-preview-synopsis" tabIndex={0}>{synopsis.text ? synopsis.content : <p className="is-empty">Este libro aún no tiene sinopsis.</p>}</div>
        </section>
        {reason && <section className="recommendation-preview-section is-reason" aria-label="Por qué te lo recomendamos">
          <h3><Sparkles aria-hidden="true" />Por qué te lo recomendamos</h3>
          <p>{reason}</p>
        </section>}
      </div>
    </div>
    <div className="recommendation-preview-footer">
      {action}
      <Link className="button primary" to={`/books/${encodeURIComponent(book.id)}`} onClick={onClose}>Ver ficha completa<ChevronRight aria-hidden="true" size={17} /></Link>
    </div>
  </dialog>, document.body)
}
