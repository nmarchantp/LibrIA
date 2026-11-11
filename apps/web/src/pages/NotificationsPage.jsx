import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, UserRoundPlus } from 'lucide-react'
import { apiRequest } from '../api/client'

export default function NotificationsPage() {
  const [result, setResult] = useState(null)
  const [offset, setOffset] = useState(0)
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setResult(null); setError('')
    apiRequest(`/me/notification-inbox?offset=${offset}`, { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setResult(data) })
      .catch(() => { if (!controller.signal.aborted) setError('No se pudieron cargar las notificaciones.') })
    return () => controller.abort()
  }, [offset, attempt])
  async function markRead(item) {
    try {
      const data = await apiRequest(`/me/notification-inbox/${item.source}/${item.id}/read`, { method: 'PUT', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      setResult(previous => previous && ({ ...previous, items: previous.items.map(row => row.id === item.id && row.source === item.source ? { ...row, read_at: data.read_at } : row) }))
      window.dispatchEvent(new Event('libria-notifications-updated'))
    } catch { setError('No se pudo marcar la notificación como leída.') }
  }
  return <section className="page-width page community-page"><span className="kicker">TU ACTIVIDAD</span><h1 className="page-title">Notificaciones</h1>
    {error && <><p role="alert">{error}</p><button className="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></>}
    {!result && !error && <p role="status">Cargando notificaciones…</p>}
    {result && <><div className="notification-list">{!result.items.length && <p><Bell size={18} /> Aún no tienes notificaciones.</p>}{result.items.map(item => <article className="notification" key={`${item.source}:${item.id}`}><span className="notification-icon">{item.source === 'follow' ? <UserRoundPlus size={20} /> : <Bell size={20} />}</span><div><h2>{item.message}</h2>{item.decision_reason && <p>Observación: {item.decision_reason}</p>}<Link className="button" to={item.href} onClick={() => { if (!item.read_at) markRead(item) }}>{item.source === 'follow' ? 'Ver perfil' : item.kind === 'requested' ? 'Revisar solicitudes' : 'Ver mi solicitud'}</Link>{!item.read_at && <button className="button" onClick={() => markRead(item)}>Marcar como leída</button>}</div><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('es-CL')}</time></article>)}</div>
      <div className="profile-social-actions">{offset > 0 && <button className="button" onClick={() => setOffset(value => Math.max(0, value - 30))}>Anterior</button>}{result.has_more && <button className="button" onClick={() => setOffset(value => value + 30)}>Siguiente</button>}</div>
    </>}
  </section>
}
