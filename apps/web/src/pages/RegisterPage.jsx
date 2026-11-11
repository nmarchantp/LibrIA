import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { profileDestination } from '../services/profileDestination'
import RegistrationPasswordFields from '../components/RegistrationPasswordFields'

export default function RegisterPage() {
  const { register } = useAuth()
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
      await register({
        display_name: form.get('name'),
        email: form.get('email'),
        password: form.get('password'),
      })
      navigate(profileDestination(params.toString()))
    } catch {
      setError('No fue posible crear la cuenta. El correo podría estar registrado.')
    } finally {
      setPending(false)
    }
  }

  return <main className="auth-page">
    <form className="auth-card" onSubmit={submit}>
      <h1>Crea tu cuenta</h1>
      <label>Nombre<input name="name" autoComplete="name" required minLength="2" maxLength="100" disabled={pending} /></label>
      <label>Correo electrónico<input name="email" type="email" autoComplete="email" required disabled={pending} /></label>
      <RegistrationPasswordFields disabled={pending} />
      {error && <p className="form-error" role="alert">{error}</p>}
      <button className="button primary" disabled={pending}>{pending ? 'Creando tu cuenta…' : 'Crear cuenta'}</button>
      <p>Después de crear tu cuenta podrás verificar tu correo y vincular Google en Mi cuenta.</p>
      <p>¿Ya tienes cuenta? <Link to={profileDestination(params.toString()) !== '/' ? `/login?next=${encodeURIComponent(profileDestination(params.toString()))}` : '/login'}>Ingresa</Link></p>
    </form>
  </main>
}
