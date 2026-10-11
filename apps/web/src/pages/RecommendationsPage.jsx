import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import BookCover from '../components/BookCover'
import { useAuth } from '../context/AuthContext'
import { apiRequest } from '../api/client'
import { normalizeGoogleBook } from '../services/booksService'

// Reuse in-flight requests during StrictMode remounts, isolated by session.
const pending = new Map()
function loadRecommendations(token, provenance) {
  const key = `${token}:${provenance}`
  if (!pending.has(key)) {
    const headers = { Authorization: `Bearer ${token}` }
    const job = apiRequest(`/analytics/me/recommendations?provenance=${provenance}`, { headers })
      .then(data => data.status === 'needs_generation' ? apiRequest('/analytics/me/recommendations', {
        method: 'POST', headers, body: JSON.stringify({ provenance }),
      }) : data).finally(() => pending.delete(key))
    pending.set(key, job)
  }
  return pending.get(key)
}

export default function RecommendationsPage() {
  const { user } = useAuth()
  const [provenance, setProvenance] = useState('unclassified')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setData(null)
    setError('')
    setLoading(true)
    const token = localStorage.getItem('libria_token')
    if (!user || !token) { setLoading(false); return () => { active = false } }
    loadRecommendations(token, provenance).then(result => {
      if (active && token === localStorage.getItem('libria_token')) setData(result)
    }).catch(cause => {
      if (!active) return
      setError(cause.status === 503 ? 'Ollama no está disponible. Inicia el modelo local y reintenta.'
        : cause.status === 409 ? 'Tus recomendaciones se están generando. Espera unos segundos y reintenta.'
        : cause.status === 429 ? 'Espera un minuto antes de generar una selección nueva.'
        : 'No se pudieron generar tus recomendaciones. Puedes reintentar.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [user, provenance, attempt])

  return <section className="page-width page community-page">
    <span className="kicker">PARA TI</span><h1 className="page-title">LibrIA te recomienda</h1>
    <p className="page-lead">Libros seleccionados por IA según tu biblioteca y los indicadores disponibles de tu ADN lector.</p>
    <label>Indicadores del ADN lector <select value={provenance} onChange={event => setProvenance(event.target.value)}>
      <option value="unclassified">Registros sin clasificación de origen</option>
      <option value="operational">Datos operacionales</option>
      <option value="simulated">Escenario ficticio de demostración</option>
    </select></label>
    {loading && <p role="status">La IA está seleccionando tus libros. La primera generación puede tardar unos minutos…</p>}
    {error && <><p className="notice" role="alert">{error}</p><button className="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></>}
    {data?.status === 'locked' && <><p className="notice">Necesitas registrar al menos {data.minimum_books} libros para usar Recomendaciones IA. Tienes {data.book_count}; te faltan {data.missing_books}.</p><p>Cuentan libros distintos en cualquier estado. Una relectura no cuenta como otro libro.</p><Link className="button primary" to="/books">Explorar y agregar libros</Link> <button className="button" onClick={() => setAttempt(value => value + 1)}>Actualizar disponibilidad</button></>}
    {data && data.status !== 'locked' && !data.has_adn && <p className="notice">Todavía no hay indicadores del ETL para el origen seleccionado. La selección usa tu biblioteca actual.</p>}
    {data?.limited_profile && <p className="notice">Aún no hay historial suficiente para personalizar: estos libros son propuestas para explorar. Registra lecturas y valoraciones para desarrollar tu ADN lector.</p>}
    {data?.provenance === 'simulated' && <p className="notice">Los indicadores seleccionados corresponden a un escenario ficticio.</p>}
    {data?.status === 'no_candidates' && <p>No hay libros nuevos disponibles para recomendarte. Explora y amplía el catálogo.</p>}
    <div className="recommendation-grid">
      {(data?.items || []).map(item => {
        const book = normalizeGoogleBook(item.volume)
        return <Link className="recommendation-card" to={`/books/${encodeURIComponent(book.id)}`} key={book.id}>
          <BookCover book={book} /><h2>{book.title}</h2><p>{book.author}</p><p>{item.reason}</p>
        </Link>
      })}
    </div>
    {data?.status === 'ready' && <p className="demo-notice"><Sparkles size={17} /> Selección de Ollama · {data.model}. Son sugerencias basadas en registros; no garantizan tus gustos.</p>}
  </section>
}
