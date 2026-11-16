import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthJourney } from '../context/AuthJourneyContext'
import { useAuth } from '../context/AuthContext'
import { profileDestination } from '../services/profileDestination'
import RegistrationPasswordFields from '../components/RegistrationPasswordFields'

export default function RegisterPage() {
  const { register } = useAuth()
  const { run: journey, motionEnabled, setMotionEnabled } = useAuthJourney()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)

  const submit = async event => {
    event.preventDefault()
    if (pending) return
    setError('')
    const form = new FormData(event.currentTarget)
    if (form.get('password') !== form.get('password_confirmation')) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setPending(true)
    try {
      await journey('library-enter', () => register({
        display_name: form.get('name'),
        email: form.get('email'),
        password: form.get('password'),
      }), () => navigate(profileDestination(params.toString())))
    } catch {
      setError('No fue posible crear la cuenta. El correo podría estar registrado.')
    } finally {
      setPending(false)
    }
  }

  return <main className="auth-page register-page">
    <div className="register-library-scene" aria-hidden="true" />
    <form className="auth-card register-card" aria-labelledby="register-heading" aria-busy={pending} onSubmit={submit}>
      <h1 id="register-heading">Crea tu cuenta</h1>
      <label>Nombre<input name="name" autoComplete="name" required minLength="2" maxLength="100" disabled={pending} /></label>
      <label>Correo electrónico<input name="email" type="email" autoComplete="email" required disabled={pending} /></label>
      <RegistrationPasswordFields disabled={pending} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="button primary" disabled={pending}>{pending ? 'Creando tu cuenta…' : 'Crear cuenta'}</button>
      <p>Después de crear tu cuenta podrás verificar tu correo y vincular Google en Mi cuenta.</p>
      <p>¿Ya tienes cuenta? <Link onClick={event => { if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; event.preventDefault(); if (!pending) journey('return', null, () => navigate(profileDestination(params.toString()) !== '/' ? `/login?next=${encodeURIComponent(profileDestination(params.toString()))}` : '/login')) }} to={profileDestination(params.toString()) !== '/' ? `/login?next=${encodeURIComponent(profileDestination(params.toString()))}` : '/login'}>Ingresa</Link></p>
    </form>
    <button className="login-motion-toggle" type="button" aria-pressed={motionEnabled} onClick={() => setMotionEnabled(value => !value)}>{motionEnabled ? 'Pausar animaciones' : 'Activar animaciones'}</button>
  </main>
}
