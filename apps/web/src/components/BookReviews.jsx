import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import './BookReviews.css'

export default function BookReviews({ bookRef }) {
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const path = `/reviews/by-book/${encodeURIComponent(bookRef)}`

  useEffect(() => {
    let active = true
    apiRequest(path).then(data => {
      if (active) { setReviews(data.items); setHasMore(data.has_more) }
    }).catch(() => { if (active) setError('No se pudieron cargar las reseñas.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [path])

  const loadMore = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest(`${path}?offset=${reviews.length}`)
      setReviews(current => [...current, ...data.items.filter(item => !current.some(review => review.id === item.id))])
      setHasMore(data.has_more)
    } catch { setError('No se pudieron cargar las reseñas.') }
    finally { setLoading(false) }
  }

  return <section className="book-reviews" aria-labelledby="book-reviews-heading">
    <h2 id="book-reviews-heading">Reseñas de los lectores</h2>
    {!loading && !error && reviews.length === 0 && <p>Aún no hay reseñas publicadas de este libro.</p>}
    {reviews.map(review => <article className="book-review" key={review.id}>
      <div className="book-review-heading"><strong>{review.author}</strong><time dateTime={review.published_at}>{new Date(review.published_at).toLocaleDateString('es-CL')}</time></div>
      {review.rating != null ? <span className="book-review-stars" role="img" aria-label={`${review.rating} de 5 estrellas`}>{'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)}</span> : <span className="book-review-unrated">Sin valoración</span>}
      {review.is_spoiler ? <details><summary>Contiene spoilers · Mostrar reseña</summary><p>{review.body}</p></details> : <p>{review.body}</p>}
    </article>)}
    {loading && <p role="status">Cargando reseñas…</p>}
    {error && <p role="alert">{error}</p>}
    {(hasMore || error) && <button className="button" type="button" disabled={loading} onClick={loadMore}>{error ? 'Reintentar' : 'Ver más reseñas'}</button>}
  </section>
}
