import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { accountRequest } from '../services/accountService'
import { API_URL } from '../api/client'
import AccountAccessSettings from './AccountAccessSettings'
import RoleManagementPanel from './RoleManagementPanel'

const labels = { lector: 'Lector', autor: 'Autor', influencer: 'Influencer', libreria: 'Librería', editorial: 'Editorial', admin: 'Administrador' }

export default function AccountManagement() {
  const { retry, endSession: closeLocalSession } = useAuth()
  const navigate = useNavigate()
  const [account, setAccount] = useState(null)
  const [sessions, setSessions] = useState([])
  const [name, setName] = useState('')
  const [biography, setBiography] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    Promise.all([accountRequest('/me'), accountRequest('/me/sessions')]).then(([data, rows]) => {
      if (active) { setAccount(data); setName(data.display_name); setBiography(data.biography || ''); setSessions(rows) }
    }).catch(cause => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [attempt])
  const run = async (operation, success, endSession = false) => {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await operation()
      setNotice(success)
      if (endSession) { closeLocalSession(); navigate('/login'); return }
      setAttempt(v => v + 1); retry()
      return result
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  const submit = (event, path, map, success, endSession = false) => {
    event.preventDefault()
    const form = event.currentTarget
    const values = Object.fromEntries(new FormData(form))
    run(async () => { const result = await accountRequest(path, 'POST', map(values)); form.reset(); return result }, success, endSession)
  }
  if (!account) return <section><p role="status">Cargando cuenta…</p>{error && <p role="alert">{error}</p>}<button onClick={() => setAttempt(v => v + 1)}>Reintentar</button></section>
  const count = Array.from(biography).length
  const password = <label>Contraseña actual<input name="current_password" type="password" autoComplete="current-password" maxLength={128} required /></label>
  return <div className="account-management">
    <section className="account-personal-info"><h2>Datos de mi cuenta</h2><p className="account-section-description">Actualiza tu nombre visible, biografía y fotografía.</p><div className="account-identity-fields">
      <label>Nombre de usuario<input value={account.username} readOnly /></label>
      <label>Tipo de perfil<input value={labels[account.role]} readOnly /></label></div>
      <form onSubmit={event => { event.preventDefault(); run(() => accountRequest('/me', 'PATCH', { display_name: name, biography: biography || null }), 'Perfil actualizado.') }}>
        <fieldset disabled={busy}><label>Nombre para mostrar<input value={name} onChange={e => setName(e.target.value)} minLength={2} maxLength={100} required /></label>
        <label>Biografía<textarea value={biography} onChange={e => setBiography(e.target.value)} aria-describedby="account-bio-count" /></label>
        <small id="account-bio-count">{count}/70 caracteres</small>
        <button className="button primary" disabled={count > 70}>Guardar perfil</button></fieldset>
      </form>
      <div className="account-photo-section"><h3>Fotografía de perfil</h3>
      {account.avatar_url && <img className="account-avatar-preview" src={account.avatar_url.startsWith('/api/') ? new URL(account.avatar_url, API_URL).href : account.avatar_url} alt="Mi fotografía de perfil" />}
      <form onSubmit={event => { event.preventDefault(); const form = event.currentTarget; const body = new FormData(form); run(() => accountRequest('/me/avatar', 'PUT', body), 'Fotografía actualizada.') }}>
        <label>Fotografía (JPEG, PNG o WebP, máximo 2 MB)<input name="file" type="file" accept="image/jpeg,image/png,image/webp" required disabled={busy} /></label>
        <div className="account-action-group"><button className="button" disabled={busy}>Subir fotografía</button>
        <button type="button" className="button" disabled={busy || !account.avatar_url} onClick={() => run(() => accountRequest('/me/avatar', 'DELETE'), 'Fotografía retirada.')}>Retirar fotografía</button></div>
      </form></div>
    </section>
    <RoleManagementPanel key={account.id} user={account} />
    <section className="account-personal-info account-security"><h2>Seguridad y acceso</h2>
      <AccountAccessSettings account={account} onUpdated={() => { setAttempt(v => v + 1); retry() }} />

      <details className="account-password-disclosure"><summary>Cambiar contraseña</summary><p>Al cambiarla se cerrarán tus sesiones.</p>
      <form onSubmit={event => submit(event, '/me/password', v => v, 'Contraseña cambiada.', true)}><fieldset disabled={busy}><h3>Cambiar contraseña</h3>{password}<label>Nueva contraseña<input name="new_password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required /></label><button className="button">Cambiar contraseña y cerrar sesiones</button></fieldset></form></details>
      <h3>Sesiones activas</h3>{sessions.length === 0 && <p>No hay sesiones activas para mostrar.</p>}{sessions.map(session => <div className="account-session-row" key={session.id}><span>Última actividad: {new Date(session.last_activity_at).toLocaleString()}</span><button type="button" className="button" disabled={busy} onClick={() => run(() => accountRequest(`/me/sessions/${session.id}`, 'DELETE'), 'Sesión cerrada.')}>Cerrar sesión</button></div>)}
    </section>
    <section className="account-personal-info account-danger"><h2>Eliminar mi cuenta</h2>
      <p>Se cerrarán todas tus sesiones y se bloqueará el uso de la aplicación. Tendrás exactamente 30 días corridos para cancelar desde la pantalla de acceso, verificando tu correo.</p>
      <p>Después del plazo se anonimizarán tus datos de cuenta. El contenido y sus relaciones se conservarán bajo “Cuenta eliminada”. El texto libre con datos personales requiere revisión separada.</p>
      <form onSubmit={event => { event.preventDefault(); const form = event.currentTarget; const values = Object.fromEntries(new FormData(form)); run(async () => { const result = await accountRequest('/me/deletion', 'POST', { current_password: values.current_password }); closeLocalSession(); navigate(`/recover-account?deadline=${encodeURIComponent(result.deletion_scheduled_at)}`) }, '') }}><fieldset disabled={busy}>{password}<label className="account-checkbox"><input type="checkbox" required /> Entiendo las consecuencias y solicito eliminar mi cuenta</label><button className="button account-danger-button">Confirmar solicitud de eliminación</button></fieldset></form>
    </section>
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
  </div>
}
