import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import GoogleLoginButton from '../components/GoogleLoginButton'

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
  const submit = async event => {
    event.preventDefault()
    setError('')
    setBusy(true)
    const form = new FormData(event.currentTarget)
    try {
      await login({ email: form.get('email'), password: form.get('password') })
      navigate('/')
    } catch {
      setError('No fue posible iniciar sesión. Revisa tus datos y que la API esté activa.')
    } finally {
      setBusy(false)
    }
  }
  return <main className="auth-page">
    <form className="auth-card" onSubmit={submit}>
      <h1>Bienvenida a LibrIAverse</h1>
      <label>Correo<input name="email" type="email" autoComplete="email" required /></label>
      <label>Contraseña<input name="password" type="password" autoComplete="current-password" required /></label>
      {(error || googleError) && <p className="form-error" role="alert">{error || googleError}</p>}
      <button className="button primary" disabled={busy}>{busy ? 'Ingresando…' : 'Ingresar'}</button>
      <p className="auth-divider">o</p>
      <GoogleLoginButton />
      <p>Para usar Google, primero verifica tu correo y vincúlalo en Mi cuenta.</p>
      <p>¿Aún no tienes cuenta? <Link to="/register">Regístrate</Link></p>
    </form>
  </main>
}
