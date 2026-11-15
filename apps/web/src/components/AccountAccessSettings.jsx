import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { accountRequest } from '../services/accountService'
import GoogleAccountPanel from './GoogleAccountPanel'

export default function AccountAccessSettings({ account, onUpdated }) {
  const { endSession } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [action, setAction] = useState(params.get('google_link') ? 'google' : null)
  const [step, setStep] = useState('request')
  const [target, setTarget] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const choose = value => { setAction(value); setStep('request'); setTarget(''); setError(''); setNotice('') }
  const submit = async event => {
    event.preventDefault()
    const values = Object.fromEntries(new FormData(event.currentTarget))
    setBusy(true); setError(''); setNotice('')
    try {
      if (action === 'unlink') {
        await accountRequest('/me/google/unlink', 'POST', values)
        endSession(); navigate('/login'); return
      }
      const change = action === 'change'
      const path = change ? '/me/email' : '/me/email/verify'
      await accountRequest(`${path}/${step === 'request' ? 'request' : 'confirm'}`, 'POST', values)
      if (step === 'request') {
        setTarget(change ? values.email : account.email); setStep('confirm')
        setNotice('Código enviado. Revisa tu bandeja de entrada y la carpeta de spam.')
      } else if (change) {
        endSession(); navigate('/login')
      } else {
        choose(null); setNotice('Correo principal verificado.'); onUpdated()
      }
    } catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }
  return <div className="account-access-settings">
    <div className="account-access-row"><div><h3>Correo de acceso</h3><p>{account.email}</p><span className="account-access-status">{account.email_verified ? 'Verificado' : 'Pendiente de verificación'}</span></div><div className="account-action-group">{!account.email_verified && <button className="button" type="button" disabled={busy} onClick={() => choose('verify')}>Verificar correo</button>}<button className="button" type="button" disabled={busy} onClick={() => choose('change')}>Cambiar correo</button></div></div>
    <div className="account-access-row"><div><h3>Acceso con Google</h3><p>{account.google_linked ? 'Vinculado: puedes iniciar sesión con Google.' : 'Opcional: vincula Google para iniciar sesión con esa cuenta.'}</p></div><button className="button" type="button" disabled={busy} onClick={() => choose(account.google_linked ? 'unlink' : 'google')}>{account.google_linked ? 'Desvincular Google' : 'Vincular Google'}</button></div>
    {action && <div className="account-access-flow">
      <div className="account-access-flow-heading"><h3>{{ verify: 'Verificar tu correo actual', change: 'Cambiar tu correo de acceso', google: 'Vincular Google', unlink: 'Desvincular Google' }[action]}</h3><button className="button text" type="button" disabled={busy} onClick={() => choose(null)}>Cerrar</button></div>
      {action === 'google' ? <GoogleAccountPanel compact /> : <>
        {action === 'unlink' ? <p>Se cerrarán tus sesiones. Necesitas una contraseña y tu correo principal verificado para conservar el acceso.</p> : step === 'request' ? <p>{action === 'change' ? 'Ingresa el nuevo correo. Te enviaremos un código allí; el actual seguirá vigente hasta que confirmes el cambio.' : `Te enviaremos un código a ${account.email} para confirmar que te pertenece.`}</p> : <p>Introduce el código enviado a <strong>{target}</strong>. {action === 'change' && 'Al confirmar, se cerrarán tus sesiones y podrás ingresar con el nuevo correo.'}</p>}
        <form key={`${action}-${step}`} onSubmit={submit}><fieldset disabled={busy}>
          {step === 'request' ? <><label>Contraseña actual<input name="current_password" type="password" autoComplete="current-password" required maxLength={128} /></label>{action === 'change' && <label>Nuevo correo<input name="email" type="email" autoComplete="email" required /></label>}</> : <label>Código recibido por correo<input name="token" autoComplete="one-time-code" minLength={32} maxLength={128} required /></label>}
          <div className="account-action-group"><button className="button primary" disabled={action === 'unlink' && !account.email_verified}>{busy ? 'Procesando…' : action === 'unlink' ? 'Desvincular y cerrar sesiones' : step === 'request' ? 'Enviar código' : action === 'change' ? 'Confirmar nuevo correo' : 'Confirmar verificación'}</button>{step === 'confirm' && <button className="button" type="button" onClick={() => { setStep('request'); setNotice(''); setError('') }}>Solicitar otro código</button>}</div>
        </fieldset></form>
        {action === 'unlink' && !account.email_verified && <p>Verifica primero tu correo de acceso.</p>}
      </>}
    </div>}
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
  </div>
}
