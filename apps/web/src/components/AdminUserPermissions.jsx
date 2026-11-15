import { useEffect, useState } from 'react'
import { accountRequest } from '../services/accountService'
import { apiRequest } from '../api/client'
import AdminProfileRoleControls from './AdminProfileRoleControls'
import InfluencerPermissionsPanel from './InfluencerPermissionsPanel'
import InfluencerApplicationDetails from './InfluencerApplicationDetails'
import AdminVerificationRequests from './AdminVerificationRequests'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })

export default function AdminUserPermissions({ user, onChanged }) {
  const [requests, setRequests] = useState([])
  const [observations, setObservations] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [reason, setReason] = useState('')
  useEffect(() => {
    let active = true
    setLoading(true)
    apiRequest(`/roles/profiles/${user.id}/requests`, { headers: headers() }).then(rows => {
      if (active) { setRequests(rows); setLoading(false); setError('') }
    }).catch(cause => { if (active) { setError(cause.message); setLoading(false) } })
    return () => { active = false }
  }, [user.id, attempt])
  const changed = result => { setAttempt(value => value + 1); onChanged(result); window.dispatchEvent(new Event('libria-notifications-updated')) }
  const mutate = async (path, body, success) => {
    setBusy(true); setError('')
    try {
      const result = await apiRequest(path, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
      const account = success ? result : await accountRequest(`/admin/${user.id}`)
      changed(account)
    } catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }
  const pending = requests.filter(request => request.status === 'pending')
  return <div className="user-permissions">
    <h3>Perfiles y permisos</h3>
    <fieldset disabled={busy || user.account_status === 'anonymized'}>
      <AdminProfileRoleControls key={`${user.id}-${user.role}`} profile={{ ...user, pending_role: pending[0]?.requested_role }} onChanged={changed} />
      {user.role === 'autor' && <section className="admin-form admin-revoke"><h3>Revocar perfil de autor</h3><p>La cuenta volverá a ser lectora. Sus publicaciones anteriores seguirán visibles.</p><label>Motivo de revocación<textarea value={reason} maxLength={1000} onChange={event => setReason(event.target.value)} rows={3} /></label><button className="button" disabled={busy || reason.trim().length < 10} onClick={() => mutate(`/roles/profiles/${user.id}/revoke`, { reason: reason.trim() }, true)}>Revocar perfil de autor</button></section>}
      <InfluencerPermissionsPanel key={`${user.id}-${user.role}`} profile={user} onChanged={changed} />
    </fieldset>
    {error && <p className="admin-message error" role="alert">{error} <button type="button" onClick={() => setAttempt(value => value + 1)}>Reintentar carga</button></p>}
    <AdminVerificationRequests requests={pending} loading={loading} observations={observations} onObservation={(id, value) => setObservations(current => ({ ...current, [id]: value }))} busy={busy || user.account_status === 'anonymized'} onDecide={(request, action) => mutate(`/roles/requests/${request.id}/${action}`, { reason: observations[request.id]?.trim() })} />
    <details className="user-request-history"><summary>Solicitudes anteriores ({requests.filter(request => request.status !== 'pending').length})</summary>{requests.filter(request => request.status !== 'pending').map(request => <article key={request.id}><strong>{request.requested_role} · {request.status === 'approved' ? 'Aprobada' : 'Rechazada'}</strong><InfluencerApplicationDetails request={request} /></article>)}</details>
  </div>
}
