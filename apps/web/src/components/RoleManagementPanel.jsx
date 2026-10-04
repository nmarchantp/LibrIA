import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'

const labels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', admin: 'Administrador' }

export default function RoleManagementPanel({ user }) {
  const { retry } = useAuth()
  const [requests, setRequests] = useState([])
  const [requestedRole, setRequestedRole] = useState('influencer')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (user.role !== 'lector') return
    let active = true
    const token = localStorage.getItem('libria_token')
    apiRequest('/roles/requests/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(data => { if (active) setRequests(data) })
      .catch(() => { if (active) setError('No se pudieron cargar tus solicitudes.') })
    return () => { active = false }
  }, [user.role, refreshKey])

  const requestRole = async event => {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    setError('')
    try {
      const token = localStorage.getItem('libria_token')
      const result = await apiRequest('/roles/requests', {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ requested_role: requestedRole, note: note.trim() }),
      })
      setRequests(current => [result, ...current])
      setNote('')
      setMessage('Solicitud enviada. Un administrador la revisará.')
    } catch (cause) {
      setError(cause.status === 409 ? 'Ya tienes una solicitud pendiente.' : 'No se pudo enviar la solicitud.')
    } finally {
      setBusy(false)
    }
  }

  return <section className="role-panel">
    <h2>Tipo de perfil: {labels[user.role]}</h2>
    {user.role === 'lector' && <>
      <p>Todos comienzan como lectores. Solicita verificación para publicar como autor o influencer.</p>
      <form className="role-form" onSubmit={requestRole}>
        <label>Solicitar perfil<select value={requestedRole} onChange={event => setRequestedRole(event.target.value)}><option value="influencer">Influencer</option><option value="autor">Autor</option></select></label>
        <label>Información para verificar tu perfil<textarea rows="3" minLength="10" maxLength="1000" value={note} onChange={event => setNote(event.target.value)} required placeholder="Cuéntanos sobre tu actividad como autor o influencer" /></label>
        <button className="button primary" disabled={busy || requests.some(item => item.status === 'pending')}>Enviar solicitud</button>
      </form>
      {requests.length > 0 && <div className="role-requests"><h3>Mis solicitudes</h3>{requests.map(request => <p key={request.id}>{labels[request.requested_role]}: {request.status === 'pending' ? 'Pendiente' : request.status === 'approved' ? 'Aprobada' : 'Rechazada'}</p>)}</div>}
      <button type="button" className="button" onClick={() => { setRefreshKey(current => current + 1); retry() }}>Actualizar estado del perfil</button>
    </>}
    {user.role === 'admin' && <p><Link className="button primary" to="/admin/profiles">Abrir mantenedor de perfiles</Link></p>}
    {(user.role === 'autor' || user.role === 'influencer' || user.role === 'libreria') && <p>Ya puedes publicar desde el mural con las opciones de tu perfil.</p>}
    {message && <p className="notice" role="status">{message}</p>}
    {error && <p className="notice" role="alert">{error}</p>}
  </section>
}
