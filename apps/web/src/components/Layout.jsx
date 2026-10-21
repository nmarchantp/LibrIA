import { Bell, BrainCircuit, CalendarDays, Compass, Database, Home, Library, LogOut, MessageCircle, Settings2, Sparkles, UserRound, BarChart3, Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiRequest } from '../api/client'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import BrandLogo from './BrandLogo'


const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', admin: 'Administrador' }

export default function Layout() {
  const { user, logout } = useAuth()
  const [groupAccess, setGroupAccess] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  useEffect(() => {
    let active = true
    apiRequest('/analytics/access', { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      .then(result => { if (active) setGroupAccess(result.group) })
      .catch(() => { if (active) setGroupAccess(false) })
    return () => { active = false }
  }, [user.id])
  const initials = user.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')
  return <div className="social-shell">
    <a className="skip-link" href="#main-content">Ir al contenido</a>
    <aside className="social-sidebar">
      <NavLink className="brand-link" to="/" aria-label="LibrIAverse, tu universo literario. Ir al mural"><BrandLogo /></NavLink>
      <button className="mobile-nav-toggle" type="button" aria-expanded={menuOpen} aria-controls="main-navigation" onClick={() => setMenuOpen(open => !open)}>{menuOpen ? <X size={22} /> : <Menu size={22} />}<span>{menuOpen ? 'Cerrar' : 'Menú'}</span></button>
      <nav id="main-navigation" className={`social-nav${menuOpen ? ' social-nav--open' : ''}`} aria-label="Navegación principal" onClick={event => { if (event.target.closest('a')) setMenuOpen(false) }} onKeyDown={event => { if (event.key === 'Escape') { setMenuOpen(false); document.querySelector('.mobile-nav-toggle')?.focus() } }}>
        <NavLink to="/" end><Home size={22} /><span>Mural</span></NavLink>
        <NavLink to="/books"><Compass size={22} /><span>Explorar libros</span></NavLink>
        <NavLink to="/library"><Library size={22} /><span>Biblioteca</span></NavLink>
        <NavLink to="/events"><CalendarDays size={22} /><span>Eventos</span></NavLink>
        <NavLink to="/messages"><MessageCircle size={22} /><span>Mensajes</span></NavLink>
        <NavLink to="/notifications"><Bell size={22} /><span>Notificaciones</span></NavLink>
        <NavLink to="/profile?tab=analysis"><BrainCircuit size={22} /><span>Tu ADN lector</span></NavLink>
        {groupAccess && <NavLink to="/insights"><BarChart3 size={22} /><span>LibrIA Insights</span></NavLink>}
        <NavLink to="/recommendations"><Sparkles size={22} /><span>Recomendaciones IA</span></NavLink>
        <NavLink to="/profile"><UserRound size={22} /><span>Mi perfil</span></NavLink>
        {user.role === 'admin' && <NavLink to="/admin/profiles"><Settings2 size={22} /><span>Gestionar perfiles</span></NavLink>}
        {user.role === 'admin' && <NavLink to="/admin/etl"><Database size={22} /><span>Carga de datos</span></NavLink>}
      </nav>
      <div className="sidebar-account"><NavLink to="/profile" className="account-link"><span className="avatar">{initials}</span><span>{user.display_name}<small>{roleLabels[user.role]}</small></span></NavLink><button className="logout-button" onClick={logout}><LogOut size={18} /> Cerrar sesión</button></div>
    </aside>
    <main id="main-content" className="social-main" tabIndex={-1}><Outlet /></main>
  </div>
}
