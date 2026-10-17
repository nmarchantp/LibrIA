import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiRequest } from '../api/client'

const messages = {
  success: 'Cuenta de Google vinculada. Ya puedes ingresar con ambos métodos.',
  cancelled: 'Cancelaste la vinculación con Google.',
  account: 'Selecciona en Google el mismo correo que verificaste. Esa cuenta no debe estar vinculada a otro usuario.',
  failed: 'No se pudo completar la vinculación. Vuelve a intentarlo.',
}
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })

export default function GoogleAccountPanel() {
  const [params] = useSearchParams()
  const [status, setStatus] = useState(null)
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [retryAt, setRetryAt] = useState(0)
  const [expiresAt, setExpiresAt] = useState(0)
  const [now, setNow] = useState(Date.now())
  const outcome = params.get('google_link')
  useEffect(() => {
    let active = true
    apiRequest('/auth/google/link', { headers: headers() })
      .then(result => { if (active) {
        setStatus(result); setEmail(result.email || ''); setError('')
        setExpiresAt(result.expires_at ? Date.parse(result.expires_at) : 0)
        setRetryAt(result.resend_at ? Date.parse(result.resend_at) : 0)
        setNow(Date.now())
      } })
      .catch(cause => { if (active) setError(cause.status === 404 ? 'El servicio de vinculación necesita actualizarse. Reinicia la API de LibrIA y pulsa Reintentar.' : cause.message) })
    return () => { active = false }
  }, [attempt, outcome])
  useEffect(() => {
    if (!retryAt && !expiresAt) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [retryAt, expiresAt])
  const seconds = Math.max(0, Math.ceil((retryAt - now) / 1000))
  const remaining = Math.max(0, Math.ceil((expiresAt - now) / 1000))
  const countdown = `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`

  const send = async event => {
    event.preventDefault()
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await apiRequest('/auth/google/email/request', { method: 'POST', headers: headers(), body: JSON.stringify({ email: email.trim() }) })
      setStatus(current => ({ ...current, email: result.email, email_verified: false, code_sent: true }))
      setCode(''); setRetryAt(Date.parse(result.resend_at)); setExpiresAt(Date.parse(result.expires_at)); setNow(Date.now())
      setMessage('Código enviado. Revisa tu bandeja de entrada y la carpeta de spam.')
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  const confirm = async event => {
    event.preventDefault()
    setBusy(true); setError(''); setMessage('')
    try {
      await apiRequest('/auth/google/email/confirm', { method: 'POST', headers: headers(), body: JSON.stringify({ code }) })
      setStatus(current => ({ ...current, email_verified: true, code_sent: false }))
      setCode(''); setExpiresAt(0); setMessage('Correo verificado. Abriendo Google para completar la vinculación…')
      await link()
    } catch (cause) { setError(cause.message) }
    finally { setBusy(false) }
  }
  const link = async () => {
    setBusy(true); setError('')
    try {
      const result = await apiRequest('/auth/google/link', { method: 'POST', credentials: 'include', headers: headers() })
      window.location.assign(result.url)
    } catch (cause) { setError(cause.message); setBusy(false) }
  }
  return <section className="google-account-panel" aria-labelledby="google-account-heading">
    <h2 id="google-account-heading">Vincular cuenta de Google</h2>
    {!status && !error && <p role="status">Consultando vinculación…</p>}
    {status?.linked ? <p role="status">Cuenta de Google vinculada: <strong>{status.email}</strong>. Puedes ingresar con Google o con tu contraseña.</p> : <>
      <p>Ingresa el correo que quieres vincular. Te enviaremos un código para verificarlo.</p>
      <form className="google-verification-form" onSubmit={send}>
        <label>Correo de tu cuenta de Google<input type="email" autoComplete="email" placeholder="tucorreo@gmail.com" value={email} onChange={event => setEmail(event.target.value)} required disabled={busy} /></label>
        <button type="submit" className="button" disabled={busy || !status || seconds > 0}>{seconds > 0 ? `Reenviar en ${seconds} s` : status?.code_sent ? 'Enviar un nuevo código' : 'Enviar código de verificación'}</button>
      </form>
      {status?.code_sent && <form className="google-verification-form" onSubmit={confirm}>
        <p>Ingresa el código enviado a <strong>{status.email}</strong>.</p>
        <p className="verification-countdown" role="timer" aria-label="Tiempo restante para verificar">Tiempo para verificar: <strong>{countdown}</strong></p>
        {remaining === 0 && <p role="alert">El código venció. Solicita uno nuevo para continuar.</p>}
        <label>Código de 6 dígitos<input value={code} onChange={event => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required disabled={busy} /></label>
        <button type="submit" className="button primary" disabled={busy || remaining === 0}>Verificar y vincular cuenta</button>
      </form>}
      {status?.email_verified && <><p>Correo verificado: <strong>{status.email}</strong>.</p>
        <button className="button primary" type="button" disabled={busy} onClick={link}>{busy ? 'Conectando…' : 'Confirmar vinculación con Google'}</button></>}
    </>}
    {messages[outcome] && <p role={outcome === 'success' ? 'status' : 'alert'}>{messages[outcome]}</p>}
    {message && <p role="status">{message}</p>}
    {error && <p role="alert">{error} {!status && <button type="button" className="button text" onClick={() => setAttempt(value => value + 1)}>Reintentar</button>}</p>}
  </section>
}
