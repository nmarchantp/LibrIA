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
    apiRequest(`/me/follow-notifications?offset=${offset}`, { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setResult(data) })
      .catch(() => { if (!controller.signal.aborted) setError('No se pudieron cargar las notificaciones.') })
    return () => controller.abort()
  }, [offset, attempt])
  async function markRead(id) {
    try {
      const data = await apiRequest(`/me/follow-notifications/${id}/read`, { method: 'PUT', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      setResult(previous => previous && ({ ...previous, items: previous.items.map(item => item.id === id ? { ...item, read_at: data.read_at } : item) }))
    } catch { setError('No se pudo marcar la notificación como leída.') }
  }
  return <section className="page-width page community-page"><span className="kicker">TU ACTIVIDAD</span><h1 className="page-title">Notificaciones</h1>
    {error && <><p role="alert">{error}</p><button className="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></>}
    {!result && !error && <p role="status">Cargando notificaciones…</p>}
    {result && <><div className="notification-list">{!result.items.length && <p><Bell size={18} /> Aún no tienes notificaciones de seguimiento.</p>}{result.items.map(item => <article className="notification" key={item.id}><span className="notification-icon"><UserRoundPlus size={20} /></span><div><h2><Link to={`/profiles/${item.profile_id}`}>{item.display_name}</Link> comenzó a seguirte</h2><p>{item.message}</p><Link className="button" to={`/profiles/${item.profile_id}`}>Ver perfil</Link>{!item.read_at && <button className="button" onClick={() => markRead(item.id)}>Marcar como leída</button>}</div><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('es-CL')}</time></article>)}</div>
      <div className="profile-social-actions">{offset > 0 && <button className="button" onClick={() => setOffset(value => Math.max(0, value - 30))}>Anterior</button>}{result.has_more && <button className="button" onClick={() => setOffset(value => value + 30)}>Siguiente</button>}</div>
    </>}
  </section>
}
