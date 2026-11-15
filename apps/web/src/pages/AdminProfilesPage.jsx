import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiRequest } from '../api/client'
import './AdminProfilesPage.css'
import AdminAccountManagement from '../components/AdminAccountManagement'
import AdminVerificationRequests from '../components/AdminVerificationRequests'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })

export default function AdminProfilesPage() {
  const [params] = useSearchParams()
  const [tab, setTab] = useState(params.get('tab') === 'requests' ? 'requests' : 'users')
  const [pending, setPending] = useState([])
  const [observations, setObservations] = useState({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [openUserId, setOpenUserId] = useState(null)
  useEffect(() => {
    let active = true
    setLoading(true)
    apiRequest('/roles/requests/pending', { headers: headers() }).then(rows => {
      if (active) { setPending(rows); setLoading(false); setError('') }
    }).catch(cause => { if (active) { setError(cause.message); setLoading(false) } })
    return () => { active = false }
  }, [refresh])
  const decide = async (request, action) => {
    setBusy(true); setError(''); setNotice('')
    try {
      await apiRequest(`/roles/requests/${request.id}/${action}`, { method: 'POST', headers: headers(), body: JSON.stringify({ reason: observations[request.id]?.trim() }) })
      setRefresh(value => value + 1)
      setNotice(action === 'approve' ? 'Perfil aprobado.' : 'Solicitud rechazada.')
      window.dispatchEvent(new Event('libria-notifications-updated'))
    } catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }
  return <div className="admin-profiles page-width">
    <header className="admin-header"><span className="kicker">ADMINISTRACIÓN</span><h1>Gestión de usuarios</h1><p>Busca un usuario y gestiona sus datos, seguridad, perfiles y solicitudes desde una sola ficha.</p></header>
    <nav className="admin-tabs" aria-label="Secciones del mantenedor"><button className={tab === 'users' ? 'active' : ''} aria-current={tab === 'users' ? 'page' : undefined} onClick={() => setTab('users')}>Usuarios</button><button className={tab === 'requests' ? 'active' : ''} aria-current={tab === 'requests' ? 'page' : undefined} onClick={() => setTab('requests')}>Solicitudes pendientes ({pending.length})</button></nav>
    <div hidden={tab !== 'users'}><AdminAccountManagement mode="unified" openUserId={openUserId} onChanged={() => setRefresh(value => value + 1)} /></div>
    {tab === 'requests' && <>
      {error && <p className="admin-message error" role="alert">{error} <button onClick={() => setRefresh(value => value + 1)}>Reintentar</button></p>}{notice && <p className="admin-message" role="status">{notice}</p>}
      <AdminVerificationRequests requests={pending} observations={observations} loading={loading} busy={busy} onObservation={(id, value) => setObservations(current => ({ ...current, [id]: value }))} onDecide={decide} onOpenUser={request => { setOpenUserId({ id: request.user_id }); setTab('users') }} />
    </>}
  </div>
}
