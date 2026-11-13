import { useState } from 'react'
import { ChevronDown, KeyRound, Mail, MonitorSmartphone, TriangleAlert } from 'lucide-react'
import { accountRequest } from '../services/accountService'
import GoogleAccountPanel from './GoogleAccountPanel'

const formatDate = value => new Date(value).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })

function PasswordInput({ placeholder = 'Contraseña actual' }) {
  return <label className="account-input"><span className="account-sr-only">Contraseña actual</span>
    <input name="current_password" type="password" autoComplete="current-password" maxLength={128} placeholder={placeholder} required />
  </label>
}

function CodeInput({ label }) {
  return <label className="account-input"><span className="account-sr-only">{label}</span>
    <input name="token" autoComplete="off" minLength={32} maxLength={128} placeholder={label} required />
  </label>
}

export default function AccountSecuritySection({ account, sessions, currentSessionId, busy, run }) {
  const [emailPanel, setEmailPanel] = useState(null)
  const [deleteConfirmed, setDeleteConfirmed] = useState(false)
  const verified = account.email_verified
  const panel = !verified || emailPanel !== 'verify' ? emailPanel : null
  const toggle = id => setEmailPanel(current => current === id ? null : id)
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
    <section className="account-card account-email-card" aria-labelledby="account-email-heading">
      <div className="account-email-row">
        <div className="account-email-copy">
          <h2 className="account-card-title" id="account-email-heading"><Mail size={18} aria-hidden="true" />Correo principal
            <span className={`account-badge ${verified ? 'is-success' : 'is-warning'}`}>{verified ? 'Verificado' : 'Pendiente de verificación'}</span></h2>
          <p className="account-email">{account.email}</p>
        </div>
        <div className="account-email-actions">
          {!verified && <button type="button" className={`button account-toggle${panel === 'verify' ? ' open' : ''} primary`} aria-expanded={panel === 'verify'} aria-controls="account-email-panel" onClick={() => toggle('verify')}>Verificar correo<ChevronDown size={16} aria-hidden="true" /></button>}
          <button type="button" className={`button account-button account-toggle${panel === 'change' ? ' open' : ''}`} aria-expanded={panel === 'change'} aria-controls="account-email-panel" onClick={() => toggle('change')}>Cambiar correo<ChevronDown size={16} aria-hidden="true" /></button>
        </div>
      </div>
      <p className="account-card-note">Los cambios de contraseña, correo o vinculación cerrarán tus sesiones activas. Luego podrás volver a ingresar.</p>
      {panel && <div className="account-email-panel" id="account-email-panel">
        {panel === 'verify' ? <>
          <form onSubmit={event => submit(event, '/me/email/verify/request', 'Te enviamos un código a tu correo principal.')}><fieldset disabled={busy}>
            <h3><span aria-hidden="true">1</span>Solicita un código</h3>
            <p>Confirma tu contraseña y enviaremos un código a <strong>{account.email}</strong>.</p>
            <PasswordInput />
            <button className="button account-button">Enviar código de verificación</button>
          </fieldset></form>
          <form onSubmit={event => submit(event, '/me/email/verify/confirm', 'Correo verificado.')}><fieldset disabled={busy}>
            <h3><span aria-hidden="true">2</span>Ingresa el código</h3>
            <p>Pega el código que recibiste. Revisa también la carpeta de spam.</p>
            <CodeInput label="Código recibido" />
            <button className="button primary account-submit">Confirmar correo principal</button>
          </fieldset></form>
        </> : <>
          <form onSubmit={event => submit(event, '/me/email/request', 'Enviamos un código al nuevo correo.')}><fieldset disabled={busy}>
            <h3><span aria-hidden="true">1</span>Indica el nuevo correo</h3>
            <p>Tu correo actual seguirá vigente hasta confirmar el nuevo.</p>
            <PasswordInput />
            <label className="account-input"><span className="account-sr-only">Nuevo correo</span><input name="email" type="email" autoComplete="email" placeholder="Nuevo correo" required /></label>
            <button className="button account-button">Verificar nuevo correo</button>
          </fieldset></form>
          <form onSubmit={event => submit(event, '/me/email/confirm', 'Correo cambiado.', '/login')}><fieldset disabled={busy}>
            <h3><span aria-hidden="true">2</span>Confirma el cambio</h3>
            <p>Ingresa el código que llegó al nuevo correo. Se cerrarán tus sesiones.</p>
            <CodeInput label="Código del nuevo correo" />
            <button className="button primary account-submit">Confirmar cambio de correo</button>
          </fieldset></form>
        </>}
      </div>}
    </section>

    <div className="account-security-grid">
      <section className="account-card" aria-labelledby="account-password-heading">
        <h2 className="account-card-title" id="account-password-heading"><KeyRound size={18} aria-hidden="true" />Cambiar contraseña</h2>
        <form className="account-stack" onSubmit={event => submit(event, '/me/password', 'Contraseña cambiada.', '/login')}><fieldset disabled={busy}>
          <PasswordInput />
          <label className="account-input"><span className="account-sr-only">Nueva contraseña</span><input name="new_password" type="password" autoComplete="new-password" minLength={8} maxLength={128} placeholder="Nueva contraseña (mínimo 8 caracteres)" required /></label>
          <button className="button account-button">Cambiar contraseña y cerrar sesiones</button>
        </fieldset></form>
      </section>
      <GoogleAccountPanel>
        {account.google_linked && <form className="account-stack account-unlink" onSubmit={event => submit(event, '/me/google/unlink', 'Google desvinculado.', '/login')}><fieldset disabled={busy}>
          <h3>Desvincular Google</h3>
          <p>Necesitas tu contraseña y el correo principal verificado para conservar el acceso.</p>
          <PasswordInput />
          <button className="button account-button" disabled={!verified}>Desvincular y cerrar sesiones</button>
        </fieldset></form>}
      </GoogleAccountPanel>
    </div>

    <section className="account-card" aria-labelledby="account-sessions-heading">
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

    <section className="account-card account-danger-card" aria-labelledby="account-delete-heading">
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
