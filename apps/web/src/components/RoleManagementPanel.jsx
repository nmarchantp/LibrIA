import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'

const labels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', admin: 'Administrador' }

export default function RoleManagementPanel({ user }) {
  const { retry } = useAuth()
  const [requests, setRequests] = useState([])
  const [requestedRole, setRequestedRole] = useState('influencer')
  const [note, setNote] = useState('')
  const [bookstore, setBookstore] = useState({ display_name: '', email: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const token = localStorage.getItem('libria_token')
  const headers = { Authorization: `Bearer ${token}` }
  const path = user.role === 'admin' ? '/roles/requests/pending' : '/roles/requests/me'

  useEffect(() => {
    let active = true
    apiRequest(path, { headers: { Authorization: `Bearer ${token}` } }).then(data => { if (active) setRequests(data) })
      .catch(() => { if (active) setError('No se pudieron cargar las solicitudes.') })
    return () => { active = false }
  }, [path, token, refreshKey])

  const execute = async (pathToCall, payload, success) => {
    setBusy(true)
    setMessage('')
    setError('')
    try {
      const result = await apiRequest(pathToCall, { method: 'POST', headers, body: JSON.stringify(payload) })
      setMessage(success)
      return result
    } catch (cause) {
      setError(cause.status === 409 ? 'La solicitud ya fue procesada o el correo ya existe.' : 'No se pudo completar la operación. Inténtalo de nuevo.')
      return null
    } finally {
      setBusy(false)
    }
  }

  const requestRole = async event => {
    event.preventDefault()
    const result = await execute('/roles/requests', { requested_role: requestedRole, note: note.trim() }, 'Solicitud enviada. Un administrador la revisará.')
    if (result) { setRequests(current => [result, ...current]); setNote('') }
  }
  const decide = async (request, action) => {
    const result = await execute(`/roles/requests/${request.id}/${action}`, {}, action === 'approve' ? 'Perfil aprobado.' : 'Solicitud rechazada.')
    if (result) setRequests(current => current.filter(item => item.id !== request.id))
  }
  const createBookstore = async event => {
    event.preventDefault()
    const result = await execute('/roles/bookstores', bookstore, 'Librería creada. Ya puede iniciar sesión.')
    if (result) setBookstore({ display_name: '', email: '', password: '' })
  }

  return <section className="role-panel">
    <h2>Tipo de perfil: {labels[user.role]}</h2>
    {user.role === 'lector' && <>
      <p>Todos comienzan como lectores. Solicita la verificación si publicas como autor o influencer.</p>
      <form className="role-form" onSubmit={requestRole}>
        <label>Solicitar perfil<select value={requestedRole} onChange={event => setRequestedRole(event.target.value)}><option value="influencer">Influencer</option><option value="autor">Autor</option></select></label>
        <label>Información para verificar tu perfil<textarea rows="3" minLength="10" maxLength="1000" value={note} onChange={event => setNote(event.target.value)} required placeholder="Cuéntanos sobre tu actividad como autor o influencer" /></label>
        <button className="button primary" disabled={busy || requests.some(item => item.status === 'pending')}>Enviar solicitud</button>
      </form>
      {requests.length > 0 && <div className="role-requests"><h3>Mis solicitudes</h3>{requests.map(request => <p key={request.id}>{labels[request.requested_role]}: {request.status === 'pending' ? 'Pendiente' : request.status === 'approved' ? 'Aprobada' : 'Rechazada'}</p>)}</div>}
      <button type="button" className="button" onClick={() => { setRefreshKey(current => current + 1); retry() }}>Actualizar estado del perfil</button>
    </>}
    {user.role === 'admin' && <>
      <h3>Solicitudes pendientes</h3>
      {requests.length === 0 && <p>No hay solicitudes pendientes.</p>}
      {requests.map(request => <article className="role-request" key={request.id}><strong>{request.display_name}</strong> · {request.email} · {labels[request.requested_role]}<p>{request.note}</p><button className="button primary" disabled={busy} onClick={() => decide(request, 'approve')}>Aprobar</button> <button className="button" disabled={busy} onClick={() => decide(request, 'reject')}>Rechazar</button></article>)}
      <h3>Crear librería</h3>
      <form className="role-form" onSubmit={createBookstore}>
        <label>Nombre<input value={bookstore.display_name} onChange={event => setBookstore(current => ({ ...current, display_name: event.target.value }))} minLength="2" required /></label>
        <label>Correo<input type="email" value={bookstore.email} onChange={event => setBookstore(current => ({ ...current, email: event.target.value }))} required /></label>
        <label>Contraseña inicial<input type="password" value={bookstore.password} onChange={event => setBookstore(current => ({ ...current, password: event.target.value }))} minLength="8" required /></label>
        <button className="button primary" disabled={busy}>Crear librería</button>
      </form>
    </>}
    {message && <p className="notice" role="status">{message}</p>}
    {error && <p className="notice" role="alert">{error}</p>}
  </section>
}
