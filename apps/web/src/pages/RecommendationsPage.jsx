import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import BookCover from '../components/BookCover'
import AiUsageBar from '../components/AiUsageBar'
import ActionStatus from '../components/ActionStatus'
import { useAuth } from '../context/AuthContext'
import { apiRequest } from '../api/client'
import { normalizeGoogleBook } from '../services/booksService'

const pending = new Map()
function readState(token) {
  if (!pending.has(token)) {
    pending.set(token, apiRequest('/analytics/me/recommendations/state', {
      headers: { Authorization: `Bearer ${token}` },
    }).finally(() => pending.delete(token)))
  }
  return pending.get(token)
}

export default function RecommendationsPage() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [requesting, setRequesting] = useState(false)

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
  const hasActiveJob = Boolean(data?.job_id) && ['pending', 'processing'].includes(generationStatus)
  const failed = generationStatus === 'failed'
  const canRequest = !budgetBlocked && !hasActiveJob && ['pending', 'outdated', 'failed'].includes(data?.status)
  const cutoff = data?.source_cutoff_at ? new Date(data.source_cutoff_at).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' }) : null

  useEffect(() => {
    if (!hasActiveJob) return undefined
    const timer = window.setInterval(() => setAttempt(value => value + 1), 5000)
    return () => window.clearInterval(timer)
  }, [hasActiveJob])

  return <section className="page-width page community-page">
    <span className="kicker">PARA TI</span><h1 className="page-title">LibrIA te recomienda</h1>
    <AiUsageBar />
    <p className="page-lead">Basta con un libro marcado como terminado y valorado con al menos 4 estrellas. Esa lectura y su valoración deben estar incluidas en la última actualización de datos para solicitar recomendaciones.</p>
    <ActionStatus busy={loading || hasActiveJob || requesting} message={requesting ? 'Registrando tu solicitud…' : loading ? 'Consultando tus recomendaciones guardadas…' : hasActiveJob ? generationStatus === 'processing' ? 'Gemini está preparando tus recomendaciones. Puede tardar más de un minuto. Aparecerán aquí automáticamente; puedes salir y volver después.' : 'Tu solicitud está en cola. No necesitas repetirla; esta página se actualizará automáticamente.' : pendingState ? 'Tus datos están preparados. Pulsa «Solicitar recomendaciones» para que Gemini elija libros para ti.' : ''} />
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
    {!hasActiveJob && data && <div><button className="button" disabled={loading || requesting} onClick={() => setAttempt(value => value + 1)}>Volver a comprobar mis datos</button><p className="demo-notice">Este botón consulta la última actualización disponible. No actualiza tus datos ni envía una solicitud a Gemini.</p></div>}
    {outdated && <p className="notice">Estas recomendaciones pertenecen a una versión anterior de tu perfil. La nueva versión está {budgetBlocked ? 'bloqueada por presupuesto' : 'pendiente'} y no se presenta como actual.</p>}
    {data?.status === 'ready' && <p>Selección actual basada en {data.positive_books_count} lectura(s) valorada(s) de tu último perfil preparado.</p>}
    <div className="recommendation-grid">
      {items.map(item => {
        const book = normalizeGoogleBook(item.volume)
        return <Link className="recommendation-card" to={`/books/${encodeURIComponent(book.id)}`} key={item.work_id || book.id}>
          <BookCover book={book} /><h2>{book.title}</h2><p>{book.author}</p><p>{item.reason}</p>
        </Link>
      })}
    </div>
    {(data?.status === 'ready' || outdated) && <p className="demo-notice"><Sparkles size={17} /> Resultado persistido de Gemini · {data.model}. Son sugerencias justificadas, no garantías de gusto.</p>}
  </section>
}
