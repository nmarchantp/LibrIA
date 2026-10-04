import { useState } from 'react'
import { Navigate, Link, useParams } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import './ReadingPage.css'

export default function ReadingPage() {
  const { id } = useParams()
  const { getBook, recordEvent, loading, loadError } = useLibrary()
  const book = getBook(id)
  const [rating, setRating] = useState(5)
  const [review, setReview] = useState('')
  const [reviewImages, setReviewImages] = useState([])
  const [reviewImageError, setReviewImageError] = useState('')
  const [page, setPage] = useState('')
  const [totalPages, setTotalPages] = useState(book?.pageCount || '')
  const [reason, setReason] = useState('')
  const [correctionReason, setCorrectionReason] = useState('')
  const [share, setShare] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const selectReviewImages = event => {
    const selected = Array.from(event.target.files || [])
    const totalSize = selected.reduce((sum, image) => sum + image.size, 0)
    if (selected.length > 10) setReviewImageError('Puedes adjuntar hasta 10 imágenes.')
    else if (selected.some(image => !['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(image.type))) setReviewImageError('Usa imágenes JPEG, PNG, GIF o WebP.')
    else if (selected.some(image => image.size > 5 * 1024 * 1024) || totalSize > 25 * 1024 * 1024) setReviewImageError('Cada imagen puede pesar hasta 5 MB y el total hasta 25 MB.')
    else { setReviewImages(selected); setReviewImageError('') }
    event.target.value = ''
  }
  if (loading) return <p role="status">Cargando biblioteca…</p>
  if (loadError) return <p role="alert">{loadError}</p>
  if (!book) return <Navigate to="/library" replace />

  const pageCount = Number(book.readingId && book.status === 'Leyendo' ? book.pageCount : totalPages)
  const bookContext = { book_ref: String(book.id), book_title: book.title }
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
      setError(cause.status === 409 ? 'Esta lectura ya tiene ese estado. Actualiza la página o registra otro avance.' : 'No se pudo guardar. Revisa los datos e inténtalo de nuevo.')
    } finally {
      setBusy(false)
    }
  }
  const submitReview = event => {
    event.preventDefault()
    const payload = { source: 'review', kind: 'reviews', ...bookContext, rating: Number(rating), body: review.trim() }
    send('/posts', payload, 'Tu reseña ya aparece en el mural.', () => {
      const form = new FormData()
      Object.entries(payload).forEach(([key, value]) => form.append(key, value))
      reviewImages.forEach(image => form.append('images', image))
      const token = localStorage.getItem('libria_token')
      return apiRequest('/posts', { method: 'POST', headers: { Authorization: 'Bearer ' + token }, body: form })
    })
  }
  const submitEvent = event => {
    event.preventDefault()
    const action = event.nativeEvent.submitter.value
    const extra = {
      page_count: pageCount,
      share,
      ...(['progress', 'correction'].includes(action) ? { current_page: Number(page) } : {}),
      ...(action === 'correction' ? { correction_reason: correctionReason.trim() } : {}),
      ...(action === 'abandon' ? { abandonment_reason: reason.trim() } : {}),
    }
    const publicEvent = ['start', 'progress', 'finish'].includes(action) || (action === 'abandon' && share)
    send('/readings/events', null, publicEvent ? 'Lectura guardada y compartida en el mural.' : 'Cambio guardado de forma privada.', () => recordEvent(book, action, extra))
  }

  return <section className="page-width page">
    <span className="kicker">EXPERIENCIA DE LECTURA</span><h1 className="page-title">{book.title}</h1>
    <p>El inicio, los avances y la finalización se muestran en el <Link to="/">mural</Link>. Puedes leer varios libros en paralelo.</p>
    <form className="experience-form" onSubmit={submitReview}>
      <h2>Escribir reseña</h2>
      <label>Valoración (1 a 5)<input type="number" min="1" max="5" value={rating} onChange={event => setRating(event.target.value)} required /></label>
      <label>Reseña<textarea rows="5" maxLength="3000" value={review} onChange={event => setReview(event.target.value)} required /></label>
      <label>Imágenes (hasta 10)<input type="file" accept="image/jpeg,image/png,image/gif,image/webp" multiple onChange={selectReviewImages} /></label>
      {reviewImages.length > 0 && <ul>{reviewImages.map((image, index) => <li key={`${image.name}-${index}`}>{image.name}</li>)}</ul>}
      {reviewImageError && <p className="notice" role="alert">{reviewImageError}</p>}
      <button className="button primary" disabled={busy || !review.trim() || Boolean(reviewImageError)}>Publicar reseña</button>
    </form>
    <form className="experience-form" onSubmit={submitEvent}>
      <h2>Avance de lectura</h2>
      <p>Inicio, avance y finalización son públicos. El abandono solo se comparte si lo eliges; los motivos permanecen privados.</p>
      <label>Total de páginas de esta edición<input type="number" min="1" disabled={Boolean(book.readingId && book.status === 'Leyendo')} value={pageCount || ''} onChange={event => setTotalPages(event.target.value)} required /></label>
      <label>Página actual (de {pageCount})<input type="number" min="0" max={pageCount - 1} value={page} onChange={event => setPage(event.target.value)} /></label>
      <label>Motivo de corrección (privado)<textarea rows="2" maxLength="1000" value={correctionReason} onChange={event => setCorrectionReason(event.target.value)} /></label>
      <label>Motivo de abandono<textarea rows="2" maxLength="1000" value={reason} onChange={event => setReason(event.target.value)} /></label>
      <label><input type="checkbox" checked={share} onChange={event => setShare(event.target.checked)} />Compartir el abandono en el mural</label>
      <div className="reading-actions">
        <button className="button" type="submit" value="start" disabled={busy || (book.readingId && book.status === 'Leyendo')}>Empezar libro</button>
        <button className="button" type="submit" value="progress" disabled={busy || !book.readingId || book.status !== 'Leyendo' || !page || Number(page) < 1 || Number(page) >= pageCount}>Registrar avance</button>
        <button className="button" type="submit" value="correction" disabled={busy || !book.readingId || book.status !== 'Leyendo' || page === '' || !correctionReason.trim()}>Corregir página hacia atrás</button>
        <button className="button" type="submit" value="finish" disabled={busy || !book.readingId || book.status !== 'Leyendo'}>Terminar libro</button>
        <button className="button" type="submit" value="abandon" disabled={busy || !book.readingId || book.status !== 'Leyendo' || !reason.trim()}>Abandonar libro</button>
      </div>
    </form>
    {message && <p className="notice" role="status">{message}</p>}
    {error && <p className="notice" role="alert">{error}</p>}
  </section>
}
