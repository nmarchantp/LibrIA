import { useEffect, useMemo, useRef, useState } from 'react'
import { BookmarkPlus, Check, ChevronRight, Info, RefreshCw, Sparkles } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import BookCover from '../components/BookCover'
import AiUsageBar from '../components/AiUsageBar'
import ActionStatus from '../components/ActionStatus'
import RatingStar from '../components/RatingStar'
import RecommendationPreview from '../components/RecommendationPreview'
import { useAuth } from '../context/AuthContext'
import { useLibrary } from '../context/LibraryContext'
import { apiRequest } from '../api/client'
import { normalizeGoogleBook } from '../services/booksService'
import './RecommendationsPage.css'

const pending = new Map()
function readState(token) {
  if (!pending.has(token)) {
    pending.set(token, apiRequest('/analytics/me/recommendations/state', {
      headers: { Authorization: `Bearer ${token}` },
    }).finally(() => pending.delete(token)))
  }
  return pending.get(token)
}

const libraryLabels = { Pendiente: 'En pendientes', Leyendo: 'Leyendo', Terminado: 'Terminado', Abandonado: 'Abandonado' }
// Same rule as the book page: some discovery results need an edition chosen there first.
const needsEdition = book => book.catalogFlow === 'discovery-v1' && !book.editionId && !book.selectionReference && !(book.editionOptional && book.workId)
// Google categories look like "Fiction / Fantasy / Epic"; the last segment is the most specific.
const genreOf = book => book.categories?.[0]?.split('/').pop().trim() || ''

function WantToRead({ book, label = 'Quiero leer' }) {
  const { getBook, addBook } = useLibrary()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const saved = getBook(book.id)
  if (saved) return <span className="recommendation-saved"><Check aria-hidden="true" />{libraryLabels[saved.status] || 'En tu biblioteca'}</span>
  const add = async () => {
    if (needsEdition(book)) { navigate(`/books/${encodeURIComponent(book.id)}`); return }
    setBusy(true); setError('')
    try { await addBook(book) } catch (cause) { setError(cause.message || 'No se pudo agregar el libro.') } finally { setBusy(false) }
  }
  return <>
    <button type="button" className="recommendation-want" disabled={busy} onClick={add}><BookmarkPlus aria-hidden="true" />{busy ? 'Agregando…' : label}</button>
    {error && <p className="recommendation-error" role="alert">{error}</p>}
  </>
}

function RecommendationCard({ item }) {
  const [open, setOpen] = useState(false)
  const [preview, setPreview] = useState(false)
  const [longReason, setLongReason] = useState(false)
  const reasonRef = useRef(null)
  const book = useMemo(() => normalizeGoogleBook(item.volume), [item.volume])
  // "Leer más" only appears when the reason really overflows its four visible lines.
  useEffect(() => {
    const node = reasonRef.current
    if (!node || open) return undefined
    const measure = () => setLongReason(node.scrollHeight > node.clientHeight + 1)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [item.reason, open])
  if (!book) return null
  const to = `/books/${encodeURIComponent(book.id)}`
  const genre = genreOf(book)
  const rating = Number(book.averageRating)
  return <article className="recommendation-card">
    <button type="button" className="recommendation-cover" tabIndex={-1} aria-hidden="true" onClick={() => setPreview(true)}>
      <BookCover book={book} />
      {genre && <span className="recommendation-badge is-genre">{genre}</span>}
      {rating > 0 && <span className="recommendation-badge is-rating"><RatingStar selected />{rating.toFixed(1)}</span>}
      {book.pageCount > 0 && <span className="recommendation-badge is-pages">{book.pageCount} pág.</span>}
      {book.year > 0 && <span className="recommendation-badge is-year">{book.year}</span>}
    </button>
    <div className="recommendation-copy">
      <h2><button type="button" className="recommendation-title" aria-haspopup="dialog" title={book.title} onClick={() => setPreview(true)}>{book.title}</button></h2>
      <p className="recommendation-author">{book.author}</p>
    </div>
    {preview && <RecommendationPreview book={book} reason={item.reason} genre={genre} action={<WantToRead book={book} label="Añadir a mi biblioteca" />} onClose={() => setPreview(false)} />}
    {item.reason && <div className="recommendation-reason-box">
      <p ref={reasonRef} className={`recommendation-reason${open ? ' is-open' : ''}`}>{item.reason}</p>
      {longReason || open ? <button type="button" className="recommendation-more" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? 'Ver menos' : 'Leer más'}</button> : <span className="recommendation-more-spacer" aria-hidden="true" />}
    </div>}
    <div className="recommendation-actions">
      <WantToRead book={book} />
      <Link className="recommendation-link" to={to}>Ver ficha<ChevronRight aria-hidden="true" /></Link>
    </div>
  </article>
}

export default function RecommendationsPage() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [requesting, setRequesting] = useState(false)
  const [showHelp, setShowHelp] = useState(false)

  async function requestRecommendations() {
    setRequesting(true); setError('')
    try {
      const token = localStorage.getItem('libria_token')
      await apiRequest('/analytics/me/recommendations/sync', {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      })
      if (token === localStorage.getItem('libria_token')) setAttempt(value => value + 1)
    } catch {
      setError('No se pudieron solicitar tus recomendaciones. Vuelve a intentarlo.')
    } finally { setRequesting(false) }
  }

  useEffect(() => {
    let active = true
    const token = localStorage.getItem('libria_token')
    setLoading(true); setError('')
    if (!user || !token) { setLoading(false); return () => { active = false } }
    readState(token).then(result => {
      if (active && token === localStorage.getItem('libria_token')) setData(result)
    }).catch(() => { if (active) setError('No se pudo consultar el estado de tus recomendaciones.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [user, attempt])

  const items = data?.items || []
  const pendingState = ['pending', 'processing'].includes(data?.status)
  const outdated = data?.status === 'outdated'
  const budgetBlocked = data?.status === 'budget_exhausted' || data?.generation_status === 'budget_exhausted'
  const generationStatus = data?.generation_status || data?.status
  const generationPaused = data?.generation_enabled === false && generationStatus !== 'processing' && ['pending', 'outdated'].includes(data?.status)
  const hasActiveJob = !generationPaused && Boolean(data?.job_id) && ['pending', 'processing'].includes(generationStatus)
  const failed = generationStatus === 'failed'
  const canRequest = data?.generation_enabled !== false && !budgetBlocked && !hasActiveJob && ['pending', 'outdated', 'failed'].includes(data?.status)
  const cutoff = data?.source_cutoff_at ? new Date(data.source_cutoff_at).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' }) : null

  useEffect(() => {
    if (!hasActiveJob) return undefined
    const timer = window.setInterval(() => setAttempt(value => value + 1), 5000)
    return () => window.clearInterval(timer)
  }, [hasActiveJob])

  return <section className="page-width page community-page recommendations-page">
    <span className="kicker recommendations-kicker"><Sparkles aria-hidden="true" />PARA TI</span><h1 className="page-title">LibrIA te recomienda</h1>
    <div className="recommendation-status">
      <div className="recommendation-status-copy">
        <AiUsageBar compact />
        {data?.status === 'ready' && <p>Selección actual basada en <strong>{data.positive_books_count} lectura(s) valorada(s)</strong> de tu último perfil preparado.</p>}
      </div>
      <div className="recommendation-status-actions">
        <button type="button" className="recommendation-chip" aria-expanded={showHelp} onClick={() => setShowHelp(value => !value)}><Info aria-hidden="true" />¿Cómo funciona?</button>
        {!hasActiveJob && data && <button type="button" className="recommendation-chip is-strong" disabled={loading || requesting} onClick={() => setAttempt(value => value + 1)} title="Consulta la última actualización disponible. No actualiza tus datos ni envía una solicitud a Gemini."><RefreshCw aria-hidden="true" />Volver a comprobar mis datos</button>}
      </div>
      {showHelp && <div className="recommendation-help">
        <p>Basta con un libro marcado como terminado y valorado con al menos 4 estrellas. Esa lectura y su valoración deben estar incluidas en la última actualización de datos para solicitar recomendaciones.</p>
        <p>«Volver a comprobar mis datos» consulta la última actualización disponible. No actualiza tus datos ni envía una solicitud a Gemini.</p>
      </div>}
    </div>
    {generationPaused && <p className="notice" role="status">La generación está desactivada. Tu solicitud está guardada; un administrador debe habilitar el servicio para continuar. Esperar en esta pantalla no iniciará el análisis.</p>}
    {!generationPaused && <ActionStatus busy={loading || hasActiveJob || requesting} message={requesting ? 'Registrando tu solicitud…' : loading ? 'Consultando tus recomendaciones guardadas…' : hasActiveJob ? generationStatus === 'processing' ? 'Gemini está preparando tus recomendaciones. Puede tardar más de un minuto. Aparecerán aquí automáticamente; puedes salir y volver después.' : 'Tu solicitud está en cola. No necesitas repetirla; esta página se actualizará automáticamente.' : pendingState ? 'Tus datos están preparados. Pulsa «Solicitar recomendaciones» para que Gemini elija libros para ti.' : ''} />}
    {error && <><p className="notice" role="alert">{error}</p><button className="button" onClick={() => setAttempt(value => value + 1)}>Reintentar consulta</button></>}
    {data?.status === 'locked' && <><p className="notice">Necesitas registrar al menos {data.minimum_books} libros. Tienes {data.book_count}; te faltan {data.missing_books}.</p><Link className="button primary" to="/books">Explorar y agregar libros</Link></>}
    {data?.status === 'waiting_for_etl' && <p className="notice">Tus datos aún no están preparados para la IA. Espera la actualización nocturna. Cuando termine, pulsa «Volver a comprobar mis datos».</p>}
    {data?.status === 'no_positive_ratings' && <div className="notice">
      <p>En la última actualización{cutoff ? `, con datos hasta el ${cutoff},` : ''} no se encontró ningún libro tuyo terminado y valorado con al menos 4 estrellas.</p>
      <p>Si ya terminaste y valoraste un libro después de ese corte, no necesitas agregar más libros ni volver a valorarlo. Espera la actualización nocturna. Después vuelve a comprobar tus datos; cuando estén preparados aparecerá «Solicitar recomendaciones».</p>
    </div>}
    {budgetBlocked && <p className="notice">El presupuesto mensual de IA está agotado. No se enviarán nuevas solicitudes hasta el siguiente periodo o una revisión administrativa.</p>}
    {failed && !budgetBlocked && <p className="notice" role="alert">No se pudieron completar tus recomendaciones. Pulsa «Reintentar recomendaciones». Si ya se alcanzó el límite de intentos, un administrador deberá revisar el problema.</p>}
    {canRequest && <button className="button primary" disabled={loading || requesting} onClick={requestRecommendations}>{failed ? 'Reintentar recomendaciones' : 'Solicitar recomendaciones'}</button>}
    {outdated && <p className="notice">Estas recomendaciones pertenecen a una versión anterior de tu perfil. La nueva versión está {budgetBlocked ? 'bloqueada por presupuesto' : 'pendiente'} y no se presenta como actual.</p>}
    {items.length > 0 && <div className="recommendation-list">
      {items.map((item, index) => <RecommendationCard item={item} key={item.work_id || item.volume?.id || index} />)}
    </div>}
    {(data?.status === 'ready' || outdated) && <p className="demo-notice"><Sparkles size={17} /> Resultado persistido de Gemini · {data.model}. Son sugerencias justificadas, no garantías de gusto.</p>}
  </section>
}
