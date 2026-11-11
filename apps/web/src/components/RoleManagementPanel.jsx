import { Link } from 'react-router-dom'
import { BadgeCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import InfluencerApplicationDetails from './InfluencerApplicationDetails'

const labels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librer?a', editorial: 'Editorial', admin: 'Administrador' }

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
  return <section className="role-panel" aria-labelledby="account-role-heading">
    <h2 id="account-role-heading"><BadgeCheck size={22} aria-hidden="true" />Tipo de perfil</h2>
    <p>Perfil asignado: <strong>{labels[user.role]}</strong></p>
    {error && <p role="alert">{error} <button type="button" onClick={() => setAttempt(value => value + 1)}>Actualizar historial</button></p>}
    {!requests && !error && <p role="status">Cargando solicitudes…</p>}
    {permissions?.suspended && <p role="status">Permisos de Influencer suspendidos hasta {new Date(permissions.until).toLocaleString('es-CL')}. Conservas tus funciones de lector.<br />Motivo: {permissions.reason}</p>}
    {user.role === 'lector' && requests && !requests.some(item => item.status === 'pending') && <form onSubmit={submit}>
      <h3>Solicitar perfil Influencer</h3><p>Conservarás tu cuenta y tus lecturas. Un administrador evaluará tu actividad.</p>
      <label>Descripción de tu actividad literaria<textarea {...field('activity_description')} minLength={10} maxLength={2000} required /></label>
      <label>Temáticas de interés (separadas por coma, máximo 10)<input {...field('topics')} maxLength={809} required /></label>
      <label>Motivación<textarea {...field('motivation')} minLength={10} maxLength={1000} required /></label>
      <label>Enlaces de tu actividad como creador (uno por línea, entre 1 y 5)<textarea {...field('evidence_links')} maxLength={10244} placeholder="https://" required /></label>
      <button className="button primary" disabled={busy}>{busy ? 'Enviando…' : 'Enviar solicitud de Influencer'}</button>
    </form>}
    {requests?.length > 0 && <div><h3>Mis solicitudes</h3>{requests.map(item => <article key={item.id}>
      <p><strong>{labels[item.requested_role]} · {{ pending: 'Pendiente', approved: 'Aprobada', rejected: 'Rechazada' }[item.status]}</strong> · {new Date(item.created_at).toLocaleString('es-CL')}</p>
      <InfluencerApplicationDetails request={item} />
    </article>)}</div>}
    {user.role === 'admin' && <Link className="button primary" to="/admin/profiles">Administrar cuentas</Link>}
  </section>
}
