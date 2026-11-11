import { useState } from 'react'
import { BookOpen, Users, Sparkles, ArrowRight, CheckCircle2 } from 'lucide-react'
import BrandLogo from '../components/BrandLogo'
import RegistrationPasswordFields from '../components/RegistrationPasswordFields'
import { authService } from '../services/authService'
import './MaintenancePage.css'

const stars = [
  [4, 12, 2, 4.8, -1], [19, 5, 3, 6.2, -4], [37, 16, 2, 5.4, -2],
  [58, 7, 2, 7.1, -5], [79, 18, 3, 5.8, -3], [95, 8, 2, 4.6, -2],
  [7, 47, 2, 6.8, -5], [49, 39, 3, 5.2, -1], [94, 54, 2, 7.4, -4],
  [3, 79, 3, 6.1, -3], [34, 88, 2, 5.7, -2], [63, 76, 2, 7.6, -6],
  [85, 92, 3, 5.3, -4], [98, 83, 2, 6.5, -1],
]

export default function MaintenancePage() {
  const [pending, setPending] = useState(false)
  const [created, setCreated] = useState(false)
  const [error, setError] = useState('')
  const submit = async event => {
    event.preventDefault()
    if (pending) return
    const form = new FormData(event.currentTarget)
    if (form.get('password') !== form.get('password_confirmation')) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setPending(true); setError('')
    try {
      await authService.register({ display_name: form.get('name'), email: form.get('email'), password: form.get('password') })
      setCreated(true)
    } catch (failure) {
      setError(failure.status === 409 ? 'Este correo ya tiene una cuenta. Podrás ingresar cuando abramos.' : failure.status === 422 ? 'Revisa tu nombre, correo y contraseña e inténtalo nuevamente.' : failure.message)
    } finally { setPending(false) }
  }
  return <main className="launch-page">
    <div className="launch-stars" aria-hidden="true">
      {stars.map(([left, top, size, duration, delay], index) => <span key={index} className={[1, 4, 7, 9, 12].includes(index) ? 'launch-star-bright' : undefined} style={{
        left: `${left}%`, top: `${top}%`, width: size, height: size,
        '--star-duration': `${duration}s`, '--star-delay': `${delay}s`,
      }} />)}
    </div>
    <header className="launch-header"><BrandLogo /><span className="launch-badge">Estamos construyendo</span></header>
    <div className="launch-grid">
      <section className="launch-story">
        <p className="launch-eyebrow">CADA LIBRO ABRE UN UNIVERSO</p>
        <h1>Tu próxima gran historia empieza <em>en comunidad.</em></h1>
        <p className="launch-intro">LibrIAverse es una nueva red social para quienes aman leer: un lugar para descubrir libros, compartir lo que te hacen sentir y conectar con personas que viven las historias como tú.</p>
        <div className="launch-features">
          <article><BookOpen aria-hidden="true" /><div><h2>Todo un universo alrededor de los libros</h2><p>Explora libros, descubre reseñas y nuevas historias, organiza tu biblioteca y lleva el recorrido de tus lecturas.</p></div></article>
          <article><Users aria-hidden="true" /><div><h2>Una comunidad con muchas voces</h2><p>Encuentra perfiles de librerías, editoriales, autores, influencers y lectores. Comparte lo que lees y conecta con quienes dan vida al mundo literario.</p></div></article>
          <article><Sparkles aria-hidden="true" /><div><h2>Inteligencia artificial para descubrir más</h2><p>La IA será parte de tu experiencia: recomendaciones según tus gustos y nuevas formas de explorar los libros y acompañar tus lecturas.</p></div></article>
        </div>
        <p className="launch-intro">Y esto es solo el comienzo. Estamos preparando muchas más novedades para que cada visita abra una nueva historia.</p>
        <p className="launch-note">Estamos trabajando en este universo. La red social todavía no está disponible, pero ya puedes crear tu cuenta para ser parte cuando abramos.</p>
      </section>
      <section className="launch-register" aria-labelledby="launch-register-title">
        {created ? <div className="launch-success" role="status"><CheckCircle2 size={44} aria-hidden="true" /><h2 id="launch-register-title">¡Ya eres parte del próximo capítulo!</h2><p>Tu cuenta fue creada correctamente. Guarda tus datos: podrás iniciar sesión cuando LibrIAverse abra sus puertas.</p><p>Por ahora, el acceso a la red social sigue cerrado.</p></div> : <>
          <span className="launch-eyebrow">SÉ PARTE DESDE EL COMIENZO</span>
          <h2 id="launch-register-title">Crea tu cuenta</h2>
          <p>Tu lugar en nuestra comunidad empieza aquí.</p>
          <form onSubmit={submit}>
            <label htmlFor="launch-name">Nombre<input id="launch-name" name="name" autoComplete="name" minLength={2} maxLength={100} required placeholder="¿Cómo te llamas?" disabled={pending} /></label>
            <label htmlFor="launch-email">Correo electrónico<input id="launch-email" name="email" type="email" autoComplete="email" required placeholder="tu@correo.cl" disabled={pending} /></label>
            <RegistrationPasswordFields disabled={pending} />
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="launch-submit" disabled={pending}>{pending ? 'Creando tu cuenta…' : 'Crear mi cuenta'}<ArrowRight size={18} aria-hidden="true" /></button>
          </form>
          <p className="launch-form-note">Crear tu cuenta no habilita el acceso todavía. Podrás iniciar sesión cuando lancemos la plataforma.</p>
        </>}
      </section>
    </div>
    <footer className="launch-footer">LibrIAverse · Tu universo literario <span>Un nuevo capítulo está por comenzar.</span></footer>
  </main>
}
