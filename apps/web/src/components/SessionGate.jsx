import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { profileDestination } from '../services/profileDestination'

export default function SessionGate({ guest = false }) {
  const { user, loading, sessionError, retry, logout } = useAuth()
  const location = useLocation()
  if (loading) return <main className="session-state" role="status">Preparando tu espacio de lectura…</main>
  if (sessionError) return <main className="session-state"><h1>No pudimos recuperar tu sesión</h1><p>Comprueba que el servidor esté activo e inténtalo nuevamente.</p><button className="button primary" onClick={retry}>Reintentar</button><button className="button text" onClick={logout}>Volver al login</button></main>
  if (guest) return user ? <Navigate to={profileDestination(location.search)} replace /> : <Outlet />
  const destination = location.pathname + location.search
  const next = profileDestination(`next=${encodeURIComponent(destination)}`)
  return user ? <Outlet /> : <Navigate to={next !== '/' ? `/login?next=${encodeURIComponent(next)}` : '/login'} replace />
}
