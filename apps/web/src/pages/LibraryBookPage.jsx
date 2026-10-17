import { useEffect, useState } from 'react'
import { ChevronLeft, CircleAlert, Droplet, Flame, Footprints, Globe2, Heart, Info, Lightbulb, MessageCircle, Save, Star, StickyNote, Users, Zap } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import BookCover from '../components/BookCover'
import ActionStatus from '../components/ActionStatus'
import AdaptiveAnalysis from '../components/AdaptiveAnalysis'
import BookReviews from '../components/BookReviews'
import { apiRequest } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import './LibraryBookPage.css'

const ratingDimensions = [
  ['general', 'General', Star], ['plot_twist', 'Plot twist', CircleAlert], ['tears', 'Lágrimas', Droplet],
  ['romance', 'Romance', Heart], ['spicy', 'Spicy', Flame], ['action', 'Acción', Zap],
  ['world_building', 'World building', Globe2], ['pace', 'Ritmo', Footprints],
]
const tabs = [['rating', 'Valoración', Star], ['notes', 'Notas', StickyNote], ['theories', 'Teorías', Lightbulb], ['community', 'Comunidad', Users]]
const formatReadingDate = value => value ? new Intl.DateTimeFormat('es-CL', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value)) : 'Añadir'

function RatingControl({ label, Icon, value, onChange }) {
  return <div className="library-rating-row">
    <span className="library-rating-label"><Icon aria-hidden="true" /><strong>{label}</strong></span>
    <span className="library-rating-buttons" role="radiogroup" aria-label={`Valoración de ${label}`}>
      {[1, 2, 3, 4, 5].map(score => <button type="button" role="radio" aria-checked={value === score}
        className={score <= value ? 'selected' : ''} key={score} onClick={() => onChange(value === score ? 0 : score)}>
        <Star aria-hidden="true" />
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

  useEffect(() => {
    if (!book) return
    setPage(book.currentPage || 0)
    setTotal(book.pageCount || 0)
    setNotebook({ characters: '', places: '', summary: '', ...(book.notebook || {}) })
  }, [book?.currentPage, book?.pageCount, book])

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

  const progress = total ? Math.min(100, Math.round((Number(book.currentPage || 0) * 100) / total)) : 0
  const genres = book.categories?.length ? book.categories : ['Sin género informado']

  const saveTotal = async () => {
    setBusy('Actualizando total de páginas…'); setError(''); setMessage('')
    try {
      await updateTotalPages(book.id, total)
      setMessage('Total de páginas actualizado.')
    } catch { setError('Revisa que el total sea válido y no sea menor que tu página actual.') }
    finally { setBusy(false) }
  }

  const saveProgress = async () => {
    setBusy('Guardando avance de lectura…'); setError(''); setMessage('')
    try {
      const nextPage = Number(page)
      const pageCount = Number(total)
      if (book.status === 'Pendiente' && nextPage === 0) await recordEvent(book, 'start', { page_count: pageCount })
      else if (nextPage === pageCount) await recordEvent(book, 'finish', { page_count: pageCount })
      else await recordEvent(book, 'progress', { current_page: nextPage, page_count: pageCount })
      setMessage('Avance guardado.')
    } catch (cause) { setError(cause.message || 'No se pudo guardar el avance.') }
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

    <section className="reading-status-strip" aria-label="Estado de la lectura">
      <div><span>ESTADO</span><strong>{book.status}</strong></div>
      <div><span>INICIO</span><strong>{formatReadingDate(book.startedAt)}</strong></div>
      <div><span>FIN</span><strong>{formatReadingDate(book.finishedAt)}</strong></div>
    </section>

    <section className="reading-book-summary">
      <BookCover book={book} large />
      <div className="reading-book-copy"><h1>{book.title}</h1><p>{book.author || 'Autor desconocido'}</p>
        <div className="library-book-genres">{genres.slice(0, 3).map(genre => <span key={genre}>{genre}</span>)}</div>
        <div className="summary-progress"><div className="library-progress-track" aria-label={`${progress}% leído`}><span style={{ width: `${progress}%` }} /></div>
          <p><strong>{progress}%</strong><span>· pág. {book.currentPage || 0} / {total || '—'}</span></p></div>
      </div>
    </section>

    <section className="compact-progress-editor" aria-label="Editar avance">
      <label>Página actual<input type="number" min={0} max={total || undefined} value={page} onChange={event => setPage(event.target.value)} disabled={book.status === 'Terminado'} /></label>
      <button className="button primary" type="button" onClick={saveProgress} disabled={busy || !total || !['Pendiente', 'Leyendo'].includes(book.status) || Number(page) < 0 || Number(page) > Number(total) || (book.status === 'Leyendo' && Number(page) <= Number(book.currentPage || 0))}>{busy === 'Guardando avance de lectura…' ? 'Guardando…' : 'Guardar avance'}</button>
      <label>Total<input type="number" min={Math.max(1, book.currentPage || 1)} value={total} onChange={event => setTotal(event.target.value)} /></label>
      <button className="icon-save-button" type="button" aria-label="Actualizar total de páginas" onClick={saveTotal} disabled={busy || !total || Number(total) === Number(book.pageCount)}><Save /></button>
    </section>

    <div className="reading-tropes"><span>◆</span><strong>Tropes y géneros</strong><p>{genres.join(' · ')}</p></div>

    <nav className="reading-tabs" aria-label="Secciones de mi lectura">
      {tabs.map(([value, label, Icon]) => <button type="button" key={value} disabled={Boolean(busy)} className={activeTab === value ? 'active' : ''} aria-pressed={activeTab === value} onClick={() => { setMessage(''); setError(''); setActiveTab(value) }}><Icon /><span>{label}</span></button>)}
    </nav>

    <ActionStatus busy={Boolean(busy)} message={busy || message} error={error} floating />

    {activeTab === 'rating' && <section className="reading-tab-content library-ratings">
      <div className="reading-section-title"><h2>Valoración</h2><Info aria-hidden="true" /></div>
      <form className="rating-form" onSubmit={saveRating} aria-busy={Boolean(busy)}>
      <div className="library-rating-grid">{ratingDimensions.map(([key, label, Icon]) => <RatingControl key={key} label={label} Icon={Icon} value={ratings[key]} onChange={value => setRatings(current => ({ ...current, [key]: value }))} />)}</div>
      <div className="review-heading"><h2>Reseña</h2><label>Visibilidad<select value={reviewVisibility} onChange={event => setReviewVisibility(event.target.value)}><option value="public">Pública</option><option value="private">Privada</option></select></label></div>
      <textarea className="reading-review-textarea" rows="6" maxLength="3000" required value={comment} onChange={event => setComment(event.target.value)} placeholder="¿Qué te ha parecido? Esta reseña puede ser pública o privada, según tus preferencias." />
      <button className="button primary reading-save-review" disabled={busy || !comment.trim() || !ratings.general}>{busy === 'Guardando valoración y reseña…' ? 'Guardando…' : existingReview ? 'Guardar valoración' : 'Crear valoración'}</button>
      {existingReview && <button className="button secondary" type="button" disabled={Boolean(busy)} onClick={deleteReview}>Eliminar mi reseña y valoración</button>}
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
