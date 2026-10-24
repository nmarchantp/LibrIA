import { ratingDimensions } from '../data/ratingDimensions'
import WorldBuildingRatingIcon from '../components/WorldBuildingRatingIcon'
import SpicyRatingIcon from '../components/SpicyRatingIcon'
import { useEffect, useId, useState } from 'react'
import { BookOpen, BookOpenCheck, CalendarDays, ChevronLeft, FileText, Flag, Info, Lightbulb, MessageCircle, PartyPopper, Save, Star, StickyNote, Tags, Users } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import BookCover from '../components/BookCover'
import ActionStatus from '../components/ActionStatus'
import AdaptiveAnalysis from '../components/AdaptiveAnalysis'
import BookReviews from '../components/BookReviews'
import { apiRequest } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import './LibraryBookPage.css'

const tabs = [['rating', 'Valoración', Star], ['notes', 'Notas', StickyNote], ['theories', 'Teorías', Lightbulb], ['community', 'Comunidad', Users]]
const formatReadingDate = value => value ? new Intl.DateTimeFormat('es-CL', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value)) : 'Añadir'

function RatingControl({ categoryKey, label, Icon, value, onChange, description, color }) {
  const descriptionId = useId()
  return <div className="library-rating-row" style={{ '--rating-category-color': color, '--rating-star-color': color }}>
    <span className="library-rating-label" title={description} tabIndex={description ? 0 : undefined} aria-describedby={description ? descriptionId : undefined}><Icon aria-hidden="true" /><strong>{label}</strong>{description && <span className="library-rating-tooltip" id={descriptionId} role="tooltip">{description} Sin valorar: sin puntuación registrada.</span>}</span>
    <span className="library-rating-buttons" role="radiogroup" aria-label={`Valoración de ${label}`} aria-describedby={description ? descriptionId : undefined}>
      {[1, 2, 3, 4, 5].map(score => <button type="button" role="radio" aria-checked={value === score}
        aria-label={`${score} de 5 en ${label}`}
        className={score <= value ? 'selected' : ''} key={score} onClick={() => onChange(value === score ? 0 : score)}>
        {categoryKey === 'world_building' ? <WorldBuildingRatingIcon selected={score <= value} /> : categoryKey === 'spicy' ? <SpicyRatingIcon selected={score <= value} /> : <Icon aria-hidden="true" stroke="var(--rating-star-color)" strokeWidth={2.3}
          fill={score <= value ? 'var(--rating-star-color)' : 'none'}
          style={{ stroke: 'var(--rating-star-color)', strokeWidth: 2.3, fill: score <= value ? 'var(--rating-star-color)' : 'none', opacity: 1 }} />}
      </button>)}
    </span>
    <span className="library-rating-value">{value ? `${value}/5` : '—'}</span>
  </div>
}

function WallComposer({ type, book }) {
  const isNote = type === 'note'
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const publish = async event => {
    event.preventDefault()
    setBusy('Publicando en tu muro…'); setError(''); setMessage('')
    try {
      await apiRequest('/posts', {
        method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` },
        body: JSON.stringify({ source: 'community', kind: 'community', publication_type: type,
          title: `${isNote ? 'Nota' : 'Teoría'} · ${book.title}`, body: body.trim(),
          book_ref: String(book.id), book_title: book.title }),
      })
      setBody('')
      setMessage(`${isNote ? 'Nota' : 'Teoría'} publicada en tu muro.`)
    } catch { setError('No se pudo publicar. Inténtalo nuevamente.') }
    finally { setBusy(false) }
  }
  const Icon = isNote ? StickyNote : Lightbulb
  return <form className={`wall-composer wall-composer--${type}`} onSubmit={publish} aria-busy={Boolean(busy)}>
    <div className="wall-composer-heading"><Icon aria-hidden="true" /><div><h3>{isNote ? 'Notas' : 'Teorías'}</h3><p>{isNote ? 'Guarda una idea como post-it visible en tu muro.' : 'Comparte una teoría para conversar con la comunidad.'}</p></div></div>
    <textarea rows="4" maxLength="500" required value={body} onChange={event => setBody(event.target.value)}
      placeholder={isNote ? 'Escribe una frase, escena o pensamiento…' : '¿Qué crees que ocurrirá o qué significa esta historia?'} />
    <div className="wall-composer-footer"><small>{body.length}/500</small><button className="button primary" disabled={busy || !body.trim()}>{busy ? 'Publicando…' : 'Publicar en mi muro'}</button></div>
    <ActionStatus busy={Boolean(busy)} message={busy || message} error={error} floating />
  </form>
}

export default function LibraryBookPage() {
  const { id } = useParams()
  const { getBook, loading, loadError, recordEvent, updateTotalPages } = useLibrary()
  const book = getBook(id)
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [ratings, setRatings] = useState(Object.fromEntries(ratingDimensions.map(([key]) => [key, 0])))
  const [comment, setComment] = useState('')
  const [existingReview, setExistingReview] = useState(null)
  const [reviewVisibility, setReviewVisibility] = useState('public')
  const [activeTab, setActiveTab] = useState('rating')
  const [notebook, setNotebook] = useState({ characters: '', places: '', summary: '' })
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { setPage(book?.currentPage ?? 0) }, [book?.readingId, book?.currentPage])
  useEffect(() => { setTotal(book?.pageCount ?? '') }, [book?.readingId, book?.pageCount])
  useEffect(() => {
    setNotebook({ characters: '', places: '', summary: '', ...(book?.notebook || {}) })
  }, [book?.readingId, book?.notebook])

  useEffect(() => {
    if (!book?.workId) return
    let active = true
    apiRequest(`/reviews/me?work_id=${book.workId}`, { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      .then(items => {
        if (!active || !items[0]) return
        const review = items[0]
        setExistingReview(review)
        setComment(review.body || '')
        setReviewVisibility(review.status === 'published' ? 'public' : 'private')
        setRatings(current => ({ ...current, ...review.dimension_ratings, general: review.rating || 0 }))
      }).catch(() => { if (active) setError('No se pudo recuperar tu valoración.') })
    return () => { active = false }
  }, [book?.workId])

  if (loading) return <section className="page-width page"><p role="status">Cargando tu libro…</p></section>
  if (loadError) return <section className="page-width page"><p role="alert">{loadError}</p></section>
  if (!book?.readingId) return <Navigate to="/profile?tab=library" replace />

  const nextPage = Number(page)
  const pageCount = Number(total)
  const savedPage = Number(book.currentPage || 0)
  const totalChanged = pageCount !== Number(book.pageCount)
  const pageChanged = nextPage !== savedPage
  const progressError = page === '' || !Number.isInteger(nextPage) || nextPage < 0
    ? 'La página actual debe ser un número entero mayor o igual a cero.'
    : total === '' || !Number.isInteger(pageCount) || pageCount < 1 || pageCount > 100000
      ? 'El total de tu edición debe ser un número entero entre 1 y 100000.'
      : pageCount < Math.max(savedPage, nextPage)
        ? 'El total de tu edición no puede ser menor que la página actual registrada o indicada.'
        : nextPage < savedPage
          ? 'Este registro solo permite avanzar: la página no puede ser menor que la ya registrada.'
          : pageChanged && !['Pendiente', 'Leyendo'].includes(book.status)
            ? 'Esta lectura está cerrada. Puedes ajustar el total de tu edición, pero no registrar nuevos avances.'
            : ''
  const progress = progressError ? 0 : Math.min(100, Math.round(nextPage * 100 / pageCount))
  const remaining = progressError ? null : pageCount - nextPage
  const genres = [...new Set([...(book.categories || []), ...(book.tropes || [])].map(item => typeof item === 'string' ? item : item?.name).filter(Boolean))]

  const saveProgress = async event => {
    event.preventDefault()
    if (progressError) { setError(progressError); return }
    if (!totalChanged && !pageChanged) return
    setBusy('Guardando avance de lectura…'); setError(''); setMessage('')
    let totalSaved = false
    try {
      let currentBook = book
      if (totalChanged) {
        const updated = await updateTotalPages(book.id, pageCount)
        currentBook = { ...book, pageCount: updated.total_pages, currentPage: updated.current_page }
        totalSaved = true
      }
      if (pageChanged) {
        if (nextPage === pageCount) await recordEvent(currentBook, 'finish', { page_count: pageCount })
        else await recordEvent(currentBook, 'progress', { current_page: nextPage, page_count: pageCount })
      }
      setMessage('Avance guardado.')
    } catch (cause) {
      setError(`${totalSaved ? 'El total de tu edición se guardó, pero no se pudo registrar el avance. Vuelve a intentarlo. ' : ''}${cause.message || 'No se pudo guardar el avance.'}`)
    }
    finally { setBusy(false) }
  }

  const saveRating = async event => {
    event.preventDefault()
    setBusy('Guardando valoración y reseña…'); setError(''); setMessage('')
    try {
      const dimensionRatings = Object.fromEntries(Object.entries(ratings).filter(([key, value]) => key !== 'general' && value))
      const targetStatus = reviewVisibility === 'public' ? 'published' : existingReview?.published_at ? 'hidden' : 'draft'
      const payload = { edition_id: book.editionId || null, rating: ratings.general || null,
        dimension_ratings: dimensionRatings, body: comment.trim(), is_spoiler: false, status: targetStatus,
        ...(!existingReview ? { work_id: book.workId } : {}) }
      const saved = await apiRequest(existingReview ? `/reviews/${existingReview.id}` : '/reviews', {
        method: existingReview ? 'PUT' : 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` },
        body: JSON.stringify(payload),
      })
      setExistingReview(saved)
      setMessage(reviewVisibility === 'public' ? 'Tu valoración quedó visible para la comunidad.' : 'Tu valoración quedó guardada de forma privada.')
    } catch { setError('No se pudo guardar la valoración.') }
    finally { setBusy(false) }
  }

  const saveNotebook = async event => {
    event.preventDefault()
    setBusy('Guardando personajes, sitios y resumen…'); setError(''); setMessage('')
    try {
      await apiRequest(`/readings/${book.readingId}/notebook`, {
        method: 'PATCH', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` },
        body: JSON.stringify(notebook),
      })
      setMessage('Tu cuaderno quedó guardado.')
    } catch { setError('No se pudo guardar el cuaderno.') }
    finally { setBusy(false) }
  }

  const deleteReview = async () => {
    setBusy('Eliminando tu reseña y valoración…'); setError(''); setMessage('')
    try {
      await apiRequest(`/reviews/${existingReview.id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      setExistingReview(null); setComment('')
      setRatings(Object.fromEntries(ratingDimensions.map(([key]) => [key, 0])))
      setMessage('Reseña y valoración eliminadas. Tu perfil se actualizará sin esa evidencia.')
    } catch { setError('No se pudo eliminar tu reseña.') }
    finally { setBusy(false) }
  }

  return <section className="page-width page library-book-page">
    <header className="reading-page-header">
      <Link className="reading-back-button" to="/profile?tab=library" aria-label="Volver a mi biblioteca"><ChevronLeft /></Link>
      <div><span className="kicker">MI ESTANTERÍA</span><strong>Mi lectura</strong></div>
      <Link className="reading-info-button" to={`/books/${book.id}`} aria-label="Ver información pública del libro"><Info /></Link>
    </header>

    <section className="reading-overview" aria-label="Resumen de tu lectura">
      <div className="reading-overview-cover"><BookCover book={book} large /></div>
      <div className="reading-overview-main">
        <div className="reading-overview-top">
          <div className="reading-book-copy"><h1>{book.title}</h1><p>{book.author || 'Autor desconocido'}</p></div>
          <section className="reading-status-strip" aria-label="Estado de la lectura">
            <div><BookOpenCheck aria-hidden="true" /><span>Estado</span><strong>{book.status}</strong></div>
            <div><CalendarDays aria-hidden="true" /><span>Inicio</span><strong>{book.startedAt ? formatReadingDate(book.startedAt) : '—'}</strong></div>
            <div><Flag aria-hidden="true" /><span>Fin</span><strong>{book.finishedAt ? formatReadingDate(book.finishedAt) : '—'}</strong></div>
          </section>
        </div>
        <form className="compact-progress-editor" aria-labelledby="reading-progress-title" aria-busy={Boolean(busy)} onSubmit={saveProgress}>
          <div className="compact-progress-visual">
            <div className="compact-progress-heading"><h2 id="reading-progress-title"><BookOpen aria-hidden="true" />Tu progreso de lectura</h2><strong>{progressError ? '—' : `${progress}%`}</strong></div>
            <progress className="compact-progress-bar" value={progress} max="100" aria-label="Porcentaje leído" />
            <div className="compact-progress-caption"><p aria-live="polite">{progressError ? 'Revisa los datos de tu edición.' : `${nextPage} de ${pageCount} páginas`}</p>
              {book.status === 'Terminado' && <span className="reading-completed">¡Libro completado!<PartyPopper aria-hidden="true" /></span>}
            </div>
            {!progressError && book.status !== 'Terminado' && <p className="compact-progress-remaining">Te quedan {remaining} páginas.</p>}
          </div>
          <div className="compact-progress-controls">
            <div className="compact-progress-fields">
              <label><span><BookOpen aria-hidden="true" />Página actual</span><input type="number" min="0" max={pageCount > 0 ? pageCount : undefined} step="1" required value={page} onChange={event => setPage(event.target.value)} disabled={Boolean(busy)} aria-describedby={progressError ? 'reading-progress-error' : undefined} /></label>
              <label><span><FileText aria-hidden="true" />Total de tu edición</span><input type="number" min="1" max="100000" step="1" required value={total} onChange={event => setTotal(event.target.value)} disabled={Boolean(busy)} aria-describedby={progressError ? 'reading-progress-error' : undefined} /></label>
            </div>
            <button className="button primary reading-save-progress" type="submit" title="Guardar avance" aria-label="Guardar avance" aria-busy={busy === 'Guardando avance de lectura…'} disabled={Boolean(busy) || Boolean(progressError) || (!totalChanged && !pageChanged)}><Save aria-hidden="true" /></button>
          </div>
          {progressError && <p className="compact-progress-error" id="reading-progress-error" role="status">{progressError}</p>}
        </form>
      </div>
      <div className="reading-tropes"><h2><Tags aria-hidden="true" />Tropes y géneros</h2><div className="reading-genre-chips">{genres.length ? genres.map(genre => <span key={genre}>{genre}</span>) : <p>Sin géneros ni tropos informados.</p>}</div></div>
    </section>

    <nav className="reading-tabs" aria-label="Secciones de mi lectura">
      {tabs.map(([value, label, Icon]) => <button type="button" key={value} disabled={Boolean(busy)} className={activeTab === value ? 'active' : ''} aria-pressed={activeTab === value} onClick={() => { setMessage(''); setError(''); setActiveTab(value) }}><Icon /><span>{label}</span></button>)}
    </nav>

    <ActionStatus busy={Boolean(busy)} message={busy || message} error={error} floating />

    {activeTab === 'rating' && <section className="reading-tab-content library-ratings">
      <form className="rating-form book-review-layout" onSubmit={saveRating} aria-busy={Boolean(busy)}>
      <section className="book-review-writing" aria-labelledby="book-review-title">
      <div className="review-heading"><h2 id="book-review-title">Reseña</h2><label>Visibilidad<select value={reviewVisibility} onChange={event => setReviewVisibility(event.target.value)}><option value="public">Pública</option><option value="private">Privada</option></select></label></div>
      <textarea className="reading-review-textarea" aria-label="Texto de tu reseña" rows="6" maxLength="3000" required value={comment} onChange={event => setComment(event.target.value)} placeholder="¿Qué te ha parecido? Esta reseña puede ser pública o privada, según tus preferencias." />
      <div className="book-review-submit">
      <button className="button primary reading-save-review" disabled={busy || !comment.trim() || !ratings.general}>{busy === 'Guardando valoración y reseña…' ? 'Guardando…' : existingReview ? 'Guardar valoración' : 'Crear valoración'}</button>
      {existingReview && <button className="button secondary" type="button" disabled={Boolean(busy)} onClick={deleteReview}>Eliminar mi reseña y valoración</button>}
      </div>
      </section>
      <section className="book-review-ratings" aria-labelledby="book-ratings-title">
      <div className="reading-section-title"><h2 id="book-ratings-title">Valoración</h2></div>
      <div className="library-rating-grid">{ratingDimensions.map(([key, label, Icon, description, color]) => <RatingControl categoryKey={key} color={color} description={description} key={key} label={label} Icon={Icon} value={ratings[key]} onChange={value => setRatings(current => ({ ...current, [key]: value }))} />)}</div>
      </section>
      </form>

      <form className="reading-notebook" onSubmit={saveNotebook} aria-busy={Boolean(busy)}>
        <label>Personajes<textarea rows="5" maxLength="3000" value={notebook.characters} onChange={event => setNotebook(current => ({ ...current, characters: event.target.value }))} placeholder="Nombres, quién es quién…" /></label>
        <label>Sitios<textarea rows="5" maxLength="3000" value={notebook.places} onChange={event => setNotebook(current => ({ ...current, places: event.target.value }))} placeholder="Lugares de la historia…" /></label>
        <label className="notebook-summary">Resumen<textarea rows="6" maxLength="5000" value={notebook.summary} onChange={event => setNotebook(current => ({ ...current, summary: event.target.value }))} placeholder="¿De qué va? Escribe tu resumen…" /></label>
        <button className="button detail-secondary" disabled={busy}><Save />{busy === 'Guardando personajes, sitios y resumen…' ? 'Guardando cuaderno…' : 'Guardar cuaderno'}</button>
      </form>
    </section>}

    {activeTab === 'notes' && <section className="reading-tab-content"><WallComposer type="note" book={book} /></section>}
    {activeTab === 'theories' && <section className="reading-tab-content"><WallComposer type="theory" book={book} /></section>}
    {existingReview?.rating ? <AdaptiveAnalysis scope="book" workId={book.workId} /> : <p className="notice">Valora este libro para ver aquí el análisis de tu experiencia con esta obra.</p>}
    {activeTab === 'community' && <section className="reading-tab-content library-community" aria-labelledby="community-title">
      <div className="library-community-heading"><MessageCircle aria-hidden="true" /><div><span className="kicker">LECTORES</span><h2 id="community-title">Comunidad</h2><p>Valoraciones y comentarios de otras personas que leyeron este libro.</p></div></div>
      <BookReviews bookRef={book.workId || id} />
    </section>}
  </section>
}
