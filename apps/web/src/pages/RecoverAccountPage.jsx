import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiRequest } from '../api/client'

export default function RecoverAccountPage() {
  const [params] = useSearchParams()
  const [purpose, setPurpose] = useState(params.get('deadline') ? 'recover_deletion' : 'password_reset')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const deadline = params.get('deadline')
  const run = async (event, path, payload, notice) => {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    const form = event.currentTarget
    try {
      const result = await apiRequest(path, { method: 'POST', __sessionRetry: true, body: JSON.stringify(payload(Object.fromEntries(new FormData(form)))) })
      setMessage(result?.suspended ? 'Eliminación cancelada. La suspensión administrativa continúa vigente; contacta al administrador.' : notice)
      form.reset()
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  return <main className="auth-page"><div className="auth-card"><h1>Recuperar acceso</h1>
    {deadline && !Number.isNaN(Date.parse(deadline)) && <p>Solicitud registrada. Puedes cancelar hasta el {new Date(deadline).toLocaleString()}. Al cumplirse ese instante termina el plazo de recuperación.</p>}
    <label>Operación<select value={purpose} onChange={e => { setPurpose(e.target.value); setMessage(''); setError('') }}><option value="password_reset">Restablecer contraseña</option><option value="recover_deletion">Cancelar eliminación de cuenta</option></select></label>
    <p>Los códigos vencen en 10 minutos y solo pueden utilizarse una vez. Recuperar una cuenta no levanta suspensiones administrativas.</p>
    <form onSubmit={event => run(event, `/accounts/recovery/request?purpose=${purpose}`, v => v, 'Si la cuenta es elegible, recibirás un correo con instrucciones.')}><fieldset disabled={busy}><label>Correo de la cuenta<input name="email" type="email" autoComplete="email" required /></label><button className="button primary">Enviar código</button></fieldset></form>
    <form onSubmit={event => run(event, purpose === 'password_reset' ? '/accounts/recovery/password' : '/accounts/recovery/deletion', v => v, purpose === 'password_reset' ? 'Contraseña restablecida. Ya puedes ingresar.' : 'Eliminación cancelada. Ya puedes ingresar.')}><fieldset disabled={busy}><label>Código recibido por correo<input name="token" autoComplete="off" minLength={32} maxLength={128} required /></label>{purpose === 'password_reset' && <label>Nueva contraseña<input name="new_password" type="password" autoComplete="new-password" minLength={8} maxLength={128} required /></label>}<button className="button primary">Confirmar recuperación</button></fieldset></form>
    {message && <p role="status">{message}</p>}{error && <p role="alert">{error}</p>}<Link to="/login">Volver al acceso</Link>
  </div></main>
}
