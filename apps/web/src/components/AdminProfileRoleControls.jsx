import { useState } from 'react'
import { accountRequest } from '../services/accountService'

const roles = { lector: 'Lector', autor: 'Autor', influencer: 'Influencer', libreria: 'Librería', editorial: 'Editorial', admin: 'Administrador' }

export default function AdminProfileRoleControls({ profile, onChanged }) {
  const [role, setRole] = useState(profile.role)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const change = async verification => {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await accountRequest(`/admin/${profile.id}/${verification ? 'verification' : 'role'}`, verification ? 'POST' : 'PATCH', verification ? { requested_role: role, note: reason.trim() } : { role, reason: reason.trim() })
      setNotice(verification ? 'Solicitud creada. Revísala en Solicitudes pendientes.' : 'Tipo de perfil actualizado.')
      onChanged(verification ? undefined : result)
    } catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }
  return <section className="admin-form">
    <h3>Tipo de perfil y verificación</h3>
    <label>Tipo de destino<select value={role} disabled={busy} onChange={event => setRole(event.target.value)}>{Object.entries(roles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <label>Motivo administrativo<textarea value={reason} onChange={event => setReason(event.target.value)} maxLength={1000} rows={3} disabled={busy} /></label>
    <small>Escribe al menos 10 caracteres. El cambio quedará registrado.</small>
    <p className="admin-inline-note">Para asignar un perfil profesional se requiere una verificación aprobada. Crear una solicitud no cambia el tipo de perfil.</p>
    <button className="button primary" disabled={busy || reason.trim().length < 10 || role === profile.role} onClick={() => change(false)}>Cambiar tipo de perfil</button>
    {['autor', 'influencer', 'libreria', 'editorial'].includes(role) && <button className="button" disabled={busy || reason.trim().length < 10 || Boolean(profile.pending_role)} onClick={() => change(true)}>Crear solicitud de verificación</button>}
    {notice && <p className="admin-message" role="status">{notice}</p>}{error && <p className="admin-message error" role="alert">{error}</p>}
  </section>
}
