import { useState } from 'react'
import { Navigate, Link, useParams } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import './ReadingPage.css'

export default function ReadingPage() {
  const { id } = useParams()
  const { getBook, recordEvent } = useLibrary()
  const book = getBook(id)
  const [rating, setRating] = useState(5)
  const [review, setReview] = useState('')
  const [page, setPage] = useState('')
  const [totalPages, setTotalPages] = useState(book?.pageCount || '')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  if (!book) return <Navigate to="/library" replace />

  const pageCount = Number(totalPages)
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
    send('/posts', { source: 'review', kind: 'reviews', ...bookContext, rating: Number(rating), body: review.trim() }, 'Tu reseña ya aparece en el mural.')
  }
  const submitEvent = event => {
    event.preventDefault()
    const action = event.nativeEvent.submitter.value
    const extra = {
      page_count: pageCount,
      ...(action === 'progress' ? { current_page: Number(page) } : {}),
      ...(action === 'abandon' ? { abandonment_reason: reason.trim() } : {}),
    }
    send('/readings/events', null, 'El avance se publicó automáticamente en el mural.', () => recordEvent(book, action, extra))
  }

  return <section className="page-width page">
    <span className="kicker">EXPERIENCIA DE LECTURA</span><h1 className="page-title">{book.title}</h1>
    <p>Las reseñas y los cambios de lectura se muestran en el <Link to="/">mural</Link>.</p>
    <form className="experience-form" onSubmit={submitReview}>
      <h2>Escribir reseña</h2>
      <label>Valoración (1 a 5)<input type="number" min="1" max="5" value={rating} onChange={event => setRating(event.target.value)} required /></label>
      <label>Reseña<textarea rows="5" maxLength="3000" value={review} onChange={event => setReview(event.target.value)} required /></label>
      <button className="button primary" disabled={busy || !review.trim()}>Publicar reseña</button>
    </form>
    <form className="experience-form" onSubmit={submitEvent}>
      <h2>Avance de lectura</h2>
      <p>Indica tu progreso y el mural generará el texto del avance.</p>
      <label>Total de páginas de esta edición<input type="number" min="1" value={totalPages} onChange={event => setTotalPages(event.target.value)} required /></label>
      <label>Página actual (de {pageCount})<input type="number" min="1" max={pageCount - 1} value={page} onChange={event => setPage(event.target.value)} /></label>
      <label>Motivo de abandono<textarea rows="2" maxLength="1000" value={reason} onChange={event => setReason(event.target.value)} /></label>
      <div className="reading-actions">
        <button className="button" type="submit" value="start" disabled={busy}>Empezar libro</button>
        <button className="button" type="submit" value="progress" disabled={busy || !page || Number(page) < 1 || Number(page) >= pageCount}>Registrar avance</button>
        <button className="button" type="submit" value="finish" disabled={busy}>Terminar libro</button>
        <button className="button" type="submit" value="abandon" disabled={busy || !reason.trim()}>Abandonar libro</button>
      </div>
    </form>
    {message && <p className="notice" role="status">{message}</p>}
    {error && <p className="notice" role="alert">{error}</p>}
  </section>
}
