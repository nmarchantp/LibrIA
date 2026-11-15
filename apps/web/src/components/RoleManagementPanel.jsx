import { Link } from 'react-router-dom'
import { UsersRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import InfluencerApplicationDetails from './InfluencerApplicationDetails'
import { roleDetails, roleLabels } from './accountRoles'

const statusLabels = { pending: ['Pendiente', 'is-warning'], approved: ['Aprobada', 'is-success'], rejected: ['Rechazada', 'is-error'] }

export default function RoleManagementPanel({ user }) {
  const [requests, setRequests] = useState(null)
  const [permissions, setPermissions] = useState(null)
  const [form, setForm] = useState({ activity_description: '', topics: '', motivation: '', evidence_links: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    const options = { signal: controller.signal, headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } }
    Promise.all([apiRequest('/roles/requests/me', options), apiRequest('/roles/me/influencer-permissions', options)])
      .then(([items, state]) => { if (!controller.signal.aborted) { setRequests(items); setPermissions(state); setError('') } })
      .catch(() => { if (!controller.signal.aborted) setError('No se pudieron cargar tus solicitudes y permisos.') })
    return () => controller.abort()
  }, [user.id, attempt])
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const payload = { requested_role: 'influencer', ...form,
        topics: form.topics.split(',').map(value => value.trim()).filter(Boolean),
        evidence_links: form.evidence_links.split('\n').map(value => value.trim()).filter(Boolean) }
      const item = await apiRequest('/roles/requests', { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, body: JSON.stringify(payload) })
      setRequests(current => [item, ...current]); setForm({ activity_description: '', topics: '', motivation: '', evidence_links: '' })
    } catch (cause) { setError(cause.status === 409 ? 'Ya existe una solicitud pendiente. Actualiza el historial.' : 'No se pudo enviar. Revisa los campos y utiliza enlaces públicos http o https, sin credenciales.') }
    finally { setBusy(false) }
  }
  const field = key => ({ value: form[key], disabled: busy, onChange: event => setForm(current => ({ ...current, [key]: event.target.value })) })
  const details = roleDetails[user.role] || roleDetails.lector
  const RoleIcon = details.icon
  return <section className="account-panel account-role-panel" aria-labelledby="account-role-heading">
    <header className="account-role-header">
      <span className="account-role-icon"><RoleIcon size={24} aria-hidden="true" /></span>
      <div className="account-role-copy">
        <h2 id="account-role-heading">Tipo de perfil <span className="account-badge is-role">{roleLabels[user.role]}</span></h2>
        <p>Perfil asignado: <strong>{roleLabels[user.role]}</strong> · {details.summary}</p>
      </div>
      {user.role === 'admin' && <Link className="button primary account-role-action" to="/admin/profiles"><UsersRound size={17} aria-hidden="true" />Administrar cuentas</Link>}
    </header>
    {permissions?.suspended && <p className="account-alert is-warning" role="status">Permisos de Influencer suspendidos hasta {new Date(permissions.until).toLocaleString('es-CL')}. Conservas tus funciones de lector.<br />Motivo: {permissions.reason}</p>}
    <ul className="account-perks">{details.perks.map(([kicker, title, text]) => <li key={title}><small>{kicker}</small><strong>{title}</strong><p>{text}</p></li>)}</ul>
    {error && <p className="account-alert is-error" role="alert">{error} <button type="button" className="button account-button" onClick={() => setAttempt(value => value + 1)}>Actualizar historial</button></p>}
    {!requests && !error && <p className="account-card-note" role="status">Cargando solicitudes…</p>}
    {user.role === 'lector' && requests && !requests.some(item => item.status === 'pending') && <form className="account-role-block account-stack" onSubmit={submit}>
      <h3>Solicitar perfil Influencer</h3><p>Conservarás tu cuenta y tus lecturas. Un administrador evaluará tu actividad.</p>
      <label className="account-field">Descripción de tu actividad literaria<textarea {...field('activity_description')} rows={3} minLength={10} maxLength={2000} required /></label>
      <label className="account-field">Temáticas de interés (separadas por coma, máximo 10)<input {...field('topics')} maxLength={809} required /></label>
      <label className="account-field">Motivación<textarea {...field('motivation')} rows={3} minLength={10} maxLength={1000} required /></label>
      <label className="account-field">Enlaces de tu actividad como creador (uno por línea, entre 1 y 5)<textarea {...field('evidence_links')} rows={3} maxLength={10244} placeholder="https://" required /></label>
      <button className="button primary account-submit" disabled={busy}>{busy ? 'Enviando…' : 'Enviar solicitud de Influencer'}</button>
    </form>}
    {requests?.length > 0 && <div className="account-role-block"><h3>Mis solicitudes</h3>
      <ul className="account-requests">{requests.map(item => {
        const [status, tone] = statusLabels[item.status] || [item.status, '']
        return <li key={item.id}>
          <p className="account-request-head"><strong>{roleLabels[item.requested_role]}</strong><span className={`account-badge ${tone}`}>{status}</span><small>{new Date(item.created_at).toLocaleString('es-CL')}</small></p>
          <InfluencerApplicationDetails request={item} />
        </li>
      })}</ul>
    </div>}
  </section>
}
