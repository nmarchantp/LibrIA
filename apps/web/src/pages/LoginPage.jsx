import { useState } from 'react'
import { Eye, EyeOff, Mail, LockKeyhole } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import GoogleLoginButton from '../components/GoogleLoginButton'
import { profileDestination } from '../services/profileDestination'
import LoginUniverse from '../components/LoginUniverse'
import './LoginPage.css'

const googleErrors = {
  cancelled: 'Cancelaste el ingreso con Google. Puedes volver a intentarlo.',
  account: 'Esta cuenta de Google no está vinculada o su correo no está verificado. Ingresa con contraseña y completa la vinculación en Mi cuenta.',
  failed: 'No fue posible ingresar con Google. Vuelve a intentarlo.',
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [error, setError] = useState('')
  const googleError = googleErrors[params.get('google_error')] || ''
  const [busy, setBusy] = useState(false)
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [motionEnabled, setMotionEnabled] = useState(true)
  const submit = async event => {
    event.preventDefault()
    setError('')
    setBusy(true)
    const form = new FormData(event.currentTarget)
    try {
      await login({ email: form.get('email'), password: form.get('password') })
      navigate(profileDestination(params.toString()))
    } catch {
      setError('No fue posible iniciar sesión. Revisa tus datos y que la API esté activa.')
    } finally {
      setBusy(false)
    }
  }
  return <main className="auth-page login-page" data-motion={motionEnabled ? 'enabled' : 'disabled'}>
    <LoginUniverse motionEnabled={motionEnabled} />
    <form className="auth-card login-card" onSubmit={submit} aria-labelledby="login-heading" aria-busy={busy}>
      <header className="login-card-heading"><h1 id="login-heading"><img className="login-wordmark" src="/images/libriaverse-wordmark.png" alt="LibrIAverse, tu universo literario" width="2172" height="724" /></h1></header>
      <label htmlFor="login-email">Correo</label><div className="login-email"><Mail size={18} aria-hidden="true" /><input id="login-email" name="email" type="email" autoComplete="email" required /></div>
      <label htmlFor="login-password">Contraseña</label>
      <div className="login-password"><LockKeyhole className="login-lock" size={18} aria-hidden="true" /><input id="login-password" name="password" type={passwordVisible ? 'text' : 'password'} autoComplete="current-password" required /><button type="button" aria-label={passwordVisible ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={passwordVisible} onClick={() => setPasswordVisible(value => !value)}>{passwordVisible ? <EyeOff size={19} aria-hidden="true" /> : <Eye size={19} aria-hidden="true" />}</button></div>
      {(error || googleError) && <p className="form-error" role="alert">{error || googleError}</p>}
      <button className="button primary" disabled={busy}>{busy ? 'Ingresando…' : 'Ingresar'}</button>
      <p className="login-recovery"><Link to="/recover-account">Recuperar contraseña o cancelar eliminación</Link></p>
      <p className="auth-divider">o</p>
      <GoogleLoginButton />
      <p className="login-google-help">Para usar Google, primero verifica tu correo y vincúlalo en Mi cuenta.</p>
      <p>¿No tienes cuenta? <Link to={profileDestination(params.toString()) !== '/' ? `/register?next=${encodeURIComponent(profileDestination(params.toString()))}` : '/register'}>Regístrate</Link></p>
    </form>
    <button className="login-motion-toggle" type="button" aria-pressed={motionEnabled} onClick={() => setMotionEnabled(value => !value)}>{motionEnabled ? 'Pausar animaciones' : 'Activar animaciones'}</button>
  </main>
}
