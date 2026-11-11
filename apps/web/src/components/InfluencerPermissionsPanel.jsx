import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
const actions = { influencer_suspended: 'Suspensión temporal', influencer_resumed: 'Reactivación', role_changed: 'Cambio de perfil' }

export default function InfluencerPermissionsPanel({ profile, onChanged }) {
  const [reason, setReason] = useState('')
  const [until, setUntil] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    apiRequest(`/accounts/admin/${profile.id}/history`, { headers: headers(), signal: controller.signal })
      .then(items => { if (!controller.signal.aborted) setHistory(items.filter(item => actions[item.action])) })
      .catch(() => { if (!controller.signal.aborted) setError('No se pudo cargar la auditoría.') })
    return () => controller.abort()
  }, [profile.id, attempt])
  async function change(action) {
    setBusy(true); setError('')
    try {
      const body = { reason: reason.trim() }
      if (action === 'influencer-suspension') body.until = new Date(until).toISOString()
      const result = await apiRequest(`/roles/profiles/${profile.id}/${action}`, { method: 'POST', headers: headers(), body: JSON.stringify(body) })
      setReason(''); setUntil(''); setAttempt(value => value + 1); onChanged(result)
    } catch { setError('No se pudo actualizar. Revisa el motivo, la fecha futura y tus permisos.') }
    finally { setBusy(false) }
  }
  return <section className="admin-form" aria-label="Permisos de Influencer">
    {profile.role === 'influencer' && <>
      <h3>Permisos de Influencer</h3>
      <p>{profile.influencer_permissions_suspended ? `Suspendidos hasta ${new Date(profile.influencer_suspended_until).toLocaleString('es-CL')}` : 'Activos'}. Las lecturas y publicaciones históricas se conservarán.</p>
      <label>Motivo de la acción<textarea value={reason} onChange={event => setReason(event.target.value)} minLength={10} maxLength={1000} disabled={busy} /></label>
      <label>Suspender hasta (hora local)<input type="datetime-local" value={until} onChange={event => setUntil(event.target.value)} disabled={busy} /></label>
      <div className="admin-request-actions">
        <button className="button" disabled={busy || reason.trim().length < 10 || !until} onClick={() => change('influencer-suspension')}>Suspender permisos</button>
        {profile.influencer_permissions_suspended && <button className="button" disabled={busy || reason.trim().length < 10} onClick={() => change('influencer-resume')}>Reactivar permisos</button>}
        <button className="button" disabled={busy || reason.trim().length < 10} onClick={() => change('revoke')}>Revocar perfil Influencer</button>
      </div>
      <p>La suspensión vence automáticamente. Revocar devuelve la cuenta a Lector.</p>
    </>}
    {error && <p role="alert">{error} <button type="button" onClick={() => setAttempt(value => value + 1)}>Actualizar auditoría</button></p>}
    <h3>Auditoría de permisos</h3>
    {history === null ? <p>Cargando auditoría…</p> : history.length ? history.map(item => <p key={item.id}><strong>{actions[item.action]}</strong> · {new Date(item.created_at).toLocaleString('es-CL')}<br />{item.reason}<br />Responsable: {item.actor_user_id}{item.after?.influencer_suspended_until && <><br />Hasta: {new Date(item.after.influencer_suspended_until).toLocaleString('es-CL')}</>}</p>) : <p>Sin acciones registradas.</p>}
  </section>
}
