import { useState } from 'react'
import { KeyRound, Mail, MonitorSmartphone, TriangleAlert } from 'lucide-react'
import { accountRequest } from '../services/accountService'
import AccountAccessSettings from './AccountAccessSettings'

const formatDate = value => new Date(value).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })

function PasswordInput({ placeholder = 'Contraseña actual' }) {
  return <label className="account-input"><span className="account-sr-only">Contraseña actual</span>
    <input name="current_password" type="password" autoComplete="current-password" maxLength={128} placeholder={placeholder} required />
  </label>
}

// Email and Google access reuse the team's AccountAccessSettings flow; the rest are this section's own cards.
export default function AccountSecuritySection({ account, sessions, currentSessionId, busy, run, reload }) {
  const [deleteConfirmed, setDeleteConfirmed] = useState(false)
  const submit = (event, path, success, redirect) => {
    event.preventDefault()
    const form = event.currentTarget
    const values = Object.fromEntries(new FormData(form))
    run(async () => { const result = await accountRequest(path, 'POST', values); form.reset(); return result }, success, redirect)
  }
  const removeAccount = event => {
    event.preventDefault()
    const { current_password } = Object.fromEntries(new FormData(event.currentTarget))
    run(() => accountRequest('/me/deletion', 'POST', { current_password }), '', result => `/recover-account?deadline=${encodeURIComponent(result.deletion_scheduled_at)}`)
  }

  return <div className="account-security">
    <section className="account-card account-personal-info account-access-card" aria-labelledby="account-access-heading">
      <h2 className="account-card-title" id="account-access-heading"><Mail size={18} aria-hidden="true" />Correo y acceso</h2>
      <p className="account-card-note">Los cambios de contraseña, correo o vinculación cerrarán tus sesiones activas. Luego podrás volver a ingresar.</p>
      <AccountAccessSettings account={account} onUpdated={reload} />
    </section>

    <section className="account-card account-personal-info" aria-labelledby="account-password-heading">
      <h2 className="account-card-title" id="account-password-heading"><KeyRound size={18} aria-hidden="true" />Cambiar contraseña</h2>
      <form className="account-stack" onSubmit={event => submit(event, '/me/password', 'Contraseña cambiada.', '/login')}><fieldset disabled={busy}>
        <PasswordInput />
        <label className="account-input"><span className="account-sr-only">Nueva contraseña</span><input name="new_password" type="password" autoComplete="new-password" minLength={8} maxLength={128} placeholder="Nueva contraseña (mínimo 8 caracteres)" required /></label>
        <button className="button account-button">Cambiar contraseña y cerrar sesiones</button>
      </fieldset></form>
    </section>

    <section className="account-card account-personal-info" aria-labelledby="account-sessions-heading">
      <h2 className="account-card-title" id="account-sessions-heading"><MonitorSmartphone size={18} aria-hidden="true" />Sesiones activas</h2>
      {sessions.length ? <ul className="account-sessions">{sessions.map(item => {
        const current = item.id === currentSessionId
        return <li key={item.id}>
          <span className="account-session-copy"><strong>{current ? 'Esta sesión' : 'Otra sesión'}{current && <span className="account-badge is-success">Actual</span>}</strong>
            <small>Última actividad: {formatDate(item.last_activity_at)}{item.created_at && ` · Iniciada: ${formatDate(item.created_at)}`}</small></span>
          <button type="button" className="button account-button" disabled={busy} onClick={() => run(() => accountRequest(`/me/sessions/${item.id}`, 'DELETE'), 'Sesión cerrada.', current ? '/login' : undefined)}>{current ? 'Cerrar esta sesión' : 'Cerrar sesión'}</button>
        </li>
      })}</ul> : <p className="account-card-note">No hay otras sesiones activas.</p>}
    </section>

    <section className="account-card account-personal-info account-danger-card" aria-labelledby="account-delete-heading">
      <h2 className="account-card-title" id="account-delete-heading"><TriangleAlert size={18} aria-hidden="true" />Eliminar mi cuenta</h2>
      <p>Se cerrarán todas tus sesiones y se bloqueará el uso de la aplicación. Tendrás exactamente <strong>30 días corridos</strong> para cancelar desde la pantalla de acceso, verificando tu correo.</p>
      <p className="account-card-note">Después del plazo se anonimizarán tus datos de cuenta. El contenido y sus relaciones se conservarán bajo “Cuenta eliminada”. El texto libre con datos personales requiere revisión separada.</p>
      <form className="account-stack" onSubmit={removeAccount}><fieldset disabled={busy}>
        <PasswordInput placeholder="Contraseña actual para confirmar" />
        <label className="account-check"><input type="checkbox" checked={deleteConfirmed} onChange={event => setDeleteConfirmed(event.target.checked)} required />Entiendo las consecuencias y solicito eliminar mi cuenta</label>
        <button className="button account-danger-button" disabled={!deleteConfirmed}>Confirmar solicitud de eliminación</button>
      </fieldset></form>
    </section>
  </div>
}
