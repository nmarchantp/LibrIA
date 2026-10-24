import RatingStar from '../components/RatingStar'
import { useEffect, useState } from 'react'
import { Navigate, Link, useParams } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import './ReadingPage.css'

const emotions = { alegria: 'Alegría', tristeza: 'Tristeza', esperanza: 'Esperanza', nostalgia: 'Nostalgia', asombro: 'Asombro', tension: 'Tensión', enojo: 'Enojo', calma: 'Calma', indiferencia: 'Indiferencia' }
const aspects = { personajes: 'Personajes', historia: 'Historia', estilo: 'Estilo de escritura', ritmo: 'Ritmo', final: 'Final', temas: 'Temas del libro' }

export default function ReadingPage() {
  const { id } = useParams()
  const { getBook, recordEvent, loading, loadError } = useLibrary()
  const book = getBook(id)
  const [rating, setRating] = useState('')
  const [review, setReview] = useState('')
  const [existingReview, setExistingReview] = useState(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewLoadError, setReviewLoadError] = useState('')
  const [isSpoiler, setIsSpoiler] = useState(false)
  const workId = book?.workId
  useEffect(() => {
    if (!workId) return
    let active = true
    setReviewLoading(true)
    setExistingReview(null)
    setReviewLoadError('')
    apiRequest(`/reviews/me?work_id=${workId}`, { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      .then(items => {
        if (!active) return
        const item = items[0] || null
        setExistingReview(item)
        setReview(item?.body || '')
        setRating(item?.rating ?? '')
        setIsSpoiler(item?.is_spoiler || false)
        setReviewLoadError('')
      }).catch(() => { if (active) setReviewLoadError('No se pudo recuperar tu reseña. Recarga antes de guardar.') })
      .finally(() => { if (active) setReviewLoading(false) })
    return () => { active = false }
  }, [workId])
  const [page, setPage] = useState('')
  const [totalPages, setTotalPages] = useState(null)
  const [reason, setReason] = useState('')
  const [correctionReason, setCorrectionReason] = useState('')
  const [share, setShare] = useState(false)
  const [selectedEmotions, setSelectedEmotions] = useState([])
  const [selectedAspects, setSelectedAspects] = useState([])
  const [sentiment, setSentiment] = useState('')
  const [reflectionText, setReflectionText] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  if (loading) return <p role="status">Cargando biblioteca…</p>
  if (loadError) return <p role="alert">{loadError}</p>
  if (!book) return <Navigate to="/library" replace />

  const pageCount = Number(book.readingId && book.status === 'Leyendo' ? book.pageCount : (totalPages?.id === id ? totalPages.value : book.pageCount))
  const canRecord = book.status === 'Pendiente' || book.status === 'Leyendo'
  const send = async (path, payload, success, request) => {
    const token = localStorage.getItem('libria_token')
    if (!token) { setError('Inicia sesión para registrar tu lectura.'); return }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await (request ? request() : apiRequest(path, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) }))
      setMessage(success)
    } catch (cause) {
      setError(cause.status === 409 ? 'Revisa que el avance supere tu página actual y sea menor al total. Si cambió el estado de la lectura, recarga la página.' : cause.status ? 'No se pudo guardar. Revisa los datos e inténtalo de nuevo.' : cause.message)
    } finally {
      setBusy(false)
    }
  }
  const submitReview = event => {
    event.preventDefault()
    const nextStatus = event.nativeEvent.submitter?.value || 'published'
    const payload = { edition_id: book.editionId || null, rating: rating === '' ? null : Number(rating),
      body: review.trim(), is_spoiler: isSpoiler, status: nextStatus,
      ...(!existingReview ? { work_id: workId } : {}) }
    const success = nextStatus === 'published' ? 'Tu reseña quedó publicada en el mural.' : nextStatus === 'draft' ? 'Borrador guardado; solo tú puedes verlo.' : 'Tu reseña quedó oculta del mural.'
    send('/reviews', payload, success, async () => {
      const token = localStorage.getItem('libria_token')
      const result = await apiRequest(existingReview ? `/reviews/${existingReview.id}` : '/reviews', {
        method: existingReview ? 'PUT' : 'POST', headers: { Authorization: 'Bearer ' + token }, body: JSON.stringify(payload) })
      if (token !== localStorage.getItem('libria_token')) throw new Error('La sesión cambió. Recarga antes de continuar.')
      setExistingReview(result)
      return result
    })
  }
  const submitEvent = event => {
    event.preventDefault()
    const action = event.nativeEvent.submitter?.value
    if (!action) return
    const extra = {
      page_count: pageCount,
      share,
      ...(['progress', 'correction'].includes(action) ? { current_page: Number(page) } : {}),
      ...(action === 'correction' ? { correction_reason: correctionReason.trim() } : {}),
      ...(action === 'abandon' ? { abandonment_reason: reason.trim() } : {}),
      ...(action === 'finish' && (selectedEmotions.length || selectedAspects.length || sentiment || reflectionText.trim()) ? {
        reflection: { emotions: selectedEmotions, aspects: selectedAspects, sentiment: sentiment || null, reflection: reflectionText.trim() },
      } : {}),
    }
    const publicEvent = ['start', 'progress', 'finish'].includes(action) || (action === 'abandon' && share)
    send('/readings/events', null, extra.reflection ? 'Libro terminado. Tu reflexión quedó privada y se incorporará al ADN lector después del ETL.' : publicEvent ? 'Lectura guardada y compartida en el mural.' : 'Cambio guardado de forma privada.', () => recordEvent(book, action, extra))
  }

  return <section className="page-width page">
    <span className="kicker">EXPERIENCIA DE LECTURA</span><h1 className="page-title">{book.title}</h1>
    <p>El inicio, los avances y la finalización se muestran en el <Link to="/">mural</Link>. Puedes leer varios libros en paralelo.</p>
    <form className="experience-form" onSubmit={submitReview}>
      <h2>{existingReview ? 'Editar mi reseña' : 'Escribir reseña'}</h2>
      {existingReview && <p>Estado: {({ draft: 'Borrador', published: 'Publicada', hidden: 'Oculta' })[existingReview.status]}. {existingReview.published_at && `Primera publicación: ${new Date(existingReview.published_at).toLocaleString('es-CL')}.`}</p>}
      {!workId && <p className="notice">Agrega este libro a tu biblioteca para escribir su reseña.</p>}
      {reviewLoading && <p role="status">Recuperando tu reseña…</p>}
      {reviewLoadError && <p className="notice" role="alert">{reviewLoadError}</p>}
      <fieldset className="review-rating" disabled={busy || reviewLoading}>
        <legend>Valoración opcional</legend>
        <div className="review-stars">
          {[1, 2, 3, 4, 5].map(value => <label className="review-star" key={value}>
            <input type="radio" name="review-rating" value={value} checked={Number(rating) === value} onChange={() => setRating(value)} aria-label={`${value} ${value === 1 ? 'estrella' : 'estrellas'}`} />
            <RatingStar selected={Number(rating) >= value} />
          </label>)}
        </div>
        <span className="review-rating-value">{rating === '' ? 'Sin valoración' : `${rating} de 5 estrellas`}</span>
        {rating !== '' && <button className="review-rating-clear" type="button" onClick={() => setRating('')}>Quitar valoración</button>}
      </fieldset>
      <label>Reseña<textarea rows="5" maxLength="3000" value={review} onChange={event => setReview(event.target.value)} required /></label>
      <label><input type="checkbox" checked={isSpoiler} onChange={event => setIsSpoiler(event.target.checked)} />Esta reseña contiene spoilers</label>
      <div className="reading-actions">
        <button className="button primary" value="published" disabled={busy || reviewLoading || !workId || !review.trim() || Boolean(reviewLoadError)}>{existingReview?.status === 'published' ? 'Guardar cambios' : 'Publicar reseña'}</button>
        {!existingReview?.published_at && <button className="button" value="draft" disabled={busy || reviewLoading || !workId || !review.trim() || Boolean(reviewLoadError)}>Guardar borrador</button>}
        {existingReview?.published_at && existingReview.status !== 'hidden' && <button className="button" value="hidden" disabled={busy || reviewLoading || !review.trim() || Boolean(reviewLoadError)}>Ocultar reseña</button>}
      </div>
    </form>
    <form className="experience-form" onSubmit={submitEvent}>
      <h2>Avance de lectura</h2>
      <p>Estado: {book.status}. Página registrada: {book.currentPage || 0}{book.pageCount ? ` de ${book.pageCount}` : ''}.</p>
      {book.status === 'Pendiente' && <p>Indica el total de páginas. Puedes empezar, registrar un avance o terminar; al registrar un avance o terminar se guardará primero el inicio de esta lectura.</p>}
      <p>Inicio, avance y finalización son públicos. El abandono solo se comparte si lo eliges; los motivos permanecen privados.</p>
      <label>Total de páginas de esta edición<input type="number" min="1" max="100000" disabled={Boolean(book.readingId && book.status === 'Leyendo')} value={pageCount || ''} onChange={event => setTotalPages({ id, value: event.target.value })} required /></label>
      <label>Página actual (de {pageCount || '?'})<input type="number" min="0" max={pageCount || undefined} value={page} onChange={event => setPage(event.target.value)} /></label>
      {pageCount > 0 && Number(page) === pageCount && <p>Llegaste a la última página: selecciona «Terminar libro».</p>}
      <label>Motivo de corrección (privado)<textarea rows="2" maxLength="1000" value={correctionReason} onChange={event => setCorrectionReason(event.target.value)} /></label>
      <label>Motivo de abandono (opcional)<textarea rows="2" maxLength="1000" value={reason} onChange={event => setReason(event.target.value)} /></label>
      <label><input type="checkbox" checked={share} onChange={event => setShare(event.target.checked)} />Compartir el abandono en el mural</label>
      {canRecord && <fieldset className="reading-reflection" disabled={busy}>
        <legend>Al terminar: ¿qué te dejó este libro?</legend>
        <p>Opcional y privado. Se guarda al seleccionar «Terminar libro». Después del ETL, Ollama usará lo que expresas para interpretar cualitativamente tu ADN lector.</p>
        <p>¿Qué emociones te produjo? Puedes elegir varias.</p>
        <div className="reflection-options">{Object.entries(emotions).map(([value, label]) => <label key={value}><input type="checkbox" checked={selectedEmotions.includes(value)} onChange={event => setSelectedEmotions(current => event.target.checked ? [...current, value] : current.filter(item => item !== value))} />{label}</label>)}</div>
        <label>¿Cómo valorarías la experiencia?<select value={sentiment} onChange={event => setSentiment(event.target.value)}><option value="">Sin indicar</option><option value="positivo">Positiva</option><option value="mixto">Mixta</option><option value="negativo">Negativa</option></select></label>
        <p>¿Qué aspectos te marcaron?</p>
        <div className="reflection-options">{Object.entries(aspects).map(([value, label]) => <label key={value}><input type="checkbox" checked={selectedAspects.includes(value)} onChange={event => setSelectedAspects(current => event.target.checked ? [...current, value] : current.filter(item => item !== value))} />{label}</label>)}</div>
        <label>Tu reflexión<textarea rows="4" maxLength="1500" value={reflectionText} onChange={event => setReflectionText(event.target.value)} placeholder="¿Qué te hizo sentir, pensar o recordar? ¿Qué te gustó o no te gustó y por qué?" /></label>
      </fieldset>}
      {book.reflection && <div className="reading-reflection"><h3>Tu reflexión privada</h3><p>{book.reflection.emotions.map(value => emotions[value]).join(' · ')}</p><p>{book.reflection.aspects.map(value => aspects[value]).join(' · ')}</p>{book.reflection.sentiment && <p>Experiencia: {({ positivo: 'Positiva', mixto: 'Mixta', negativo: 'Negativa' })[book.reflection.sentiment]}</p>}<p>{book.reflection.reflection}</p><small>Disponible para tu análisis después de la próxima carga del ETL.</small></div>}
      <div className="reading-actions">
        <button className="button" type="submit" value="start" disabled={busy || (book.readingId && book.status === 'Leyendo')}>Empezar libro</button>
        <button className="button" type="submit" value="progress" disabled={busy || !canRecord || !page || Number(page) <= (book.currentPage || 0) || Number(page) >= pageCount}>Registrar avance</button>
        <button className="button" type="submit" value="correction" disabled={busy || !book.readingId || book.status !== 'Leyendo' || page === '' || !correctionReason.trim()}>Corregir página hacia atrás</button>
        <button className="button" type="submit" value="finish" disabled={busy || !canRecord}>Terminar libro</button>
        <button className="button" type="submit" value="abandon" disabled={busy || !book.readingId || book.status !== 'Leyendo'}>Abandonar libro</button>
      </div>
    </form>
    {message && <p className="notice" role="status">{message}</p>}
    {error && <p className="notice" role="alert">{error}</p>}
  </section>
}
