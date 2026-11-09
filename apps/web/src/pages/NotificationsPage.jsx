import { Bell, Check } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { moderationRequest, moderationError, statusLabels } from '../services/moderation'
import '../components/Moderation.css'

export default function NotificationsPage() {
  const { user } = useAuth()
  const [result, setData] = useState(null), [offset, setOffset] = useState(0), [epoch, setEpoch] = useState(0)
  const data = result?.owner === user.id ? result : null
  const [error, setError] = useState(''), [busy, setBusy] = useState(null)
  const sending = useRef(false)
  useEffect(() => {
    const controller = new AbortController()
    setError('')
    moderationRequest(`/me/notifications?limit=20&offset=${offset}`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setData({ ...value, owner: user.id }) }).catch(cause => { if (!controller.signal.aborted) setError(moderationError(cause)) })
    return () => controller.abort()
  }, [user.id, offset, epoch])
  async function read(id) {
    if (sending.current) return
    sending.current = true; setBusy(id)
    try { await moderationRequest(`/me/notifications/${id}/read`, { method: 'PUT' }); setEpoch(value => value + 1) }
    catch (cause) { setError(moderationError(cause)) }
    finally { sending.current = false; setBusy(null) }
  }
  return <section className="page-width page community-page">
    <span className="kicker">TU ACTIVIDAD</span><h1 className="page-title">Notificaciones</h1>
    <p>Decisiones y estados privados de tus contenidos.{data && ` ${data.unread_count} sin leer.`}</p>
    {error && <p role="alert">{error} <button onClick={() => setEpoch(value => value + 1)}>Reintentar</button></p>}
    {!data && !error && <p role="status">Cargando notificaciones...</p>}
    {data && <><div className="notification-list">
      {!data.items.length && <p>No tienes notificaciones de moderación.</p>}
      {data.items.map(item => <article className="notification" key={item.id}>
        <span className="notification-icon"><Bell size={20} /></span><div><h2>{statusLabels[item.kind]}</h2><p>{item.message}</p>{item.decision_reason && <p>Motivo: {item.decision_reason}</p>}<Link to={`/settings?tab=publications&revision=${item.revision_id}`}>Consultar contenido privado</Link>{!item.read_at && <button type="button" disabled={busy === item.id} onClick={() => read(item.id)}><Check size={15} />Marcar como leída</button>}</div><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('es-CL')}</time>
      </article>)}
    </div><div className="moderation-pagination"><button disabled={!offset} onClick={() => setOffset(value => Math.max(0, value - 20))}>Anterior</button><button disabled={!data.has_more} onClick={() => setOffset(value => value + 20)}>Siguiente</button></div></>}
  </section>
}
