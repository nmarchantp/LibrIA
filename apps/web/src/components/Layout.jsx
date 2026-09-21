import { Bell, BookOpen, BrainCircuit, CalendarDays, Compass, Home, Library, LogOut, MessageCircle, Sparkles, UserRound } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const { user, logout } = useAuth()
  const initials = user.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')
  return <div className="social-shell">
    <aside className="social-sidebar">
      <NavLink className="brand" to="/" aria-label="LibrIA, mural"><span className="brand-icon"><BookOpen size={21} /></span><span>Libr<span>IA</span></span></NavLink>
      <p className="sidebar-caption">Historias que nos conectan</p>
      <nav className="social-nav" aria-label="Navegación principal">
        <NavLink to="/" end><Home size={22} /><span>Mural</span></NavLink>
        <NavLink to="/books"><Compass size={22} /><span>Explorar libros</span></NavLink>
        <NavLink to="/library"><Library size={22} /><span>Biblioteca</span></NavLink>
        <NavLink to="/events"><CalendarDays size={22} /><span>Eventos</span></NavLink>
        <NavLink to="/messages"><MessageCircle size={22} /><span>Mensajes</span></NavLink>
        <NavLink to="/notifications"><Bell size={22} /><span>Notificaciones</span></NavLink>
        <NavLink to="/insights"><BrainCircuit size={22} /><span>Tu ADN lector</span></NavLink>
        <NavLink to="/recommendations"><Sparkles size={22} /><span>Recomendaciones IA</span></NavLink>
        <NavLink to="/profile"><UserRound size={22} /><span>Mi perfil</span></NavLink>
      </nav>
      <div className="sidebar-account"><NavLink to="/profile" className="account-link"><span className="avatar">{initials}</span><span>{user.display_name}<small>Mi espacio lector</small></span></NavLink><button className="logout-button" onClick={logout}><LogOut size={18} /> Cerrar sesión</button></div>
    </aside>
    <main className="social-main"><Outlet /></main>
  </div>
}
