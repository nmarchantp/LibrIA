import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import BookCover from '../components/BookCover'
import ActionStatus from '../components/ActionStatus'
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

function ReaderRecommendations() {
  const { user } = useAuth()
  const provenance = 'unclassified'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [moreLoading, setMoreLoading] = useState(false)
  const [moreError, setMoreError] = useState('')
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

  async function requestMore() {
    setMoreLoading(true); setMoreError('')
    const token = localStorage.getItem('libria_token')
    try {
      const result = await apiRequest('/analytics/me/recommendations', {
        method:'POST', headers:{Authorization:`Bearer ${token}`},
        body:JSON.stringify({provenance,exclude_ids:(data?.items || []).map(item => String(item.volume.id))}),
      })
      if (token !== localStorage.getItem('libria_token')) return
      setData(current => {
        if (result.status === 'no_positive_ratings' || result.status === 'locked') return result
        const seen = new Set(current.items.map(item => String(item.volume.id)))
        return {...result, status:result.status === 'no_candidates' ? current.status : result.status,
          items:[...current.items,...result.items.filter(item => !seen.has(String(item.volume.id)))]}
      })
    } catch(cause) {
      if(token !== localStorage.getItem('libria_token')) return
      setMoreError(cause.status===429 ? 'Has pedido varias tandas seguidas. Espera un minuto y vuelve a intentarlo.'
        : cause.status===409 ? 'Tu perfil o tus recomendaciones se están actualizando. Espera unos segundos y reintenta.'
        : 'No se pudieron obtener más opciones. Tus recomendaciones anteriores se conservan.')
    } finally { if(token === localStorage.getItem('libria_token')) setMoreLoading(false) }
  }

  return <section className="page-width page community-page">
    <span className="kicker">PARA TI</span><h1 className="page-title">LibrIA te recomienda</h1>
    <p className="page-lead">Ollama analiza los libros que valoraste con 4 o 5 estrellas, tus reseñas y tus apreciaciones para seleccionar nuevas lecturas.</p>
    <ActionStatus busy={loading} message={loading ? 'Consultando tu biblioteca y preparando recomendaciones… La primera generación puede tardar unos minutos.' : !moreLoading && data?.status === 'ready' ? 'Consulta completada. Tus recomendaciones están listas.' : ''} />
    {error && <><p className="notice" role="alert">{error}</p><button className="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></>}
    {data?.status === 'locked' && <><p className="notice">Necesitas registrar al menos {data.minimum_books} libros para usar Recomendaciones IA. Tienes {data.book_count}; te faltan {data.missing_books}.</p><p>Cuentan libros distintos en cualquier estado. Una relectura no cuenta como otro libro.</p><Link className="button primary" to="/books">Explorar y agregar libros</Link> <button className="button" onClick={() => setAttempt(value => value + 1)}>Actualizar disponibilidad</button></>}
    {data?.status === 'no_positive_ratings' && <p className="notice">Valora al menos un libro de tu biblioteca con 4 o 5 estrellas para recibir recomendaciones basadas en lo que te gustó. No se asume que terminar un libro significa que te gustó.</p>}
    {data?.status === 'ready' && <p>Selección basada en {data.positive_books_count} libro(s) bien valorados de tu biblioteca. Puedes pedir otras opciones sin perder las anteriores.</p>}
    {data?.status === 'no_candidates' && <p>No hay libros nuevos disponibles para recomendarte. Explora y amplía el catálogo.</p>}
    <div className="recommendation-grid">
      {(data?.items || []).map(item => {
        const book = normalizeGoogleBook(item.volume)
        return <Link className="recommendation-card" to={`/books/${encodeURIComponent(book.id)}`} key={book.id}>
          <BookCover book={book} /><h2>{book.title}</h2><p>{book.author}</p><p>{item.reason}</p>
        </Link>
      })}
    </div>
    <ActionStatus busy={moreLoading} message={moreLoading ? 'Ollama está buscando otras opciones según tus libros favoritos…' : ''} error={moreError} />
    {data?.status === 'ready' && data.has_more && <button className="button primary" disabled={loading || moreLoading} onClick={requestMore}>{moreLoading ? 'Buscando más opciones…' : moreError ? 'Reintentar más recomendaciones' : 'Recomendarme más opciones'}</button>}
    {data?.status === 'ready' && !data.has_more && <p role="status">Ya viste las opciones disponibles en el catálogo actual. A medida que se incorporen más libros, habrá nuevas alternativas.</p>}
    {data?.status === 'ready' && <p className="demo-notice"><Sparkles size={17} /> Selección de Ollama · {data.model}. Son sugerencias basadas en registros; no garantizan tus gustos.</p>}
  </section>
}

export default function RecommendationsPage() {
  const {user} = useAuth()
  return <ReaderRecommendations key={user?.id} />
}
