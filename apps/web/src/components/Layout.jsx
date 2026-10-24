import { CalendarDays, Database, Home, LogOut, Settings2, UserRound, BarChart3, Menu, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { apiRequest } from '../api/client'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import BrandLogo from './BrandLogo'
import NavigationIcon from './NavigationIcon'
import NavigationGalaxy from './NavigationGalaxy'
import MessageBubbleIcon from './MessageBubbleIcon'
import NotificationBellIcon from './NotificationBellIcon'
import HeaderGreeting from './HeaderGreeting'
import './LayoutNavigation.css'


const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', admin: 'Administrador' }

function HeaderShortcut({ to, label, icon: Icon }) {
  const tooltipId = useId()
  return <NavLink to={to} className="global-header-action" aria-label={label} aria-describedby={tooltipId}>
    <Icon size={21} aria-hidden="true" /><span id={tooltipId} className="global-header-tooltip" role="tooltip">{label}</span>
  </NavLink>
}

export default function Layout() {
  const { user, logout } = useAuth()
  const [groupAccess, setGroupAccess] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const toolsRef = useRef(null)
  const { pathname, search } = useLocation()
  const hasTools = groupAccess || user.role === 'admin'
  useEffect(() => {
    setMenuOpen(false)
    if (toolsRef.current) toolsRef.current.open = false
  }, [pathname, search])
  useEffect(() => {
    const dismissTools = event => {
      if (toolsRef.current && !toolsRef.current.contains(event.target)) toolsRef.current.open = false
    }
    document.addEventListener('pointerdown', dismissTools)
    return () => document.removeEventListener('pointerdown', dismissTools)
  }, [])
  useEffect(() => {
    let active = true
    apiRequest('/analytics/access', { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      .then(result => { if (active) setGroupAccess(result.group) })
      .catch(() => { if (active) setGroupAccess(false) })
    return () => { active = false }
  }, [user.id])
  const initials = user.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')
  return <div className={`social-shell${hasTools ? ' has-navigation-tools' : ''}`}>
    <a className="skip-link" href="#main-content">Ir al contenido</a>
    <aside className="social-sidebar">
      <Link className="brand-link" to="/" aria-label="LibrIAverse, tu universo literario. Ir al mural"><BrandLogo /></Link>
      <button className="mobile-nav-toggle" type="button" aria-label={menuOpen ? 'Cerrar menú principal' : 'Abrir menú principal'} aria-expanded={menuOpen} aria-controls="main-navigation" onClick={() => setMenuOpen(open => !open)}>{menuOpen ? <X size={22} /> : <Menu size={22} />}<span>{menuOpen ? 'Cerrar' : 'Menú'}</span></button>
      <div className={`sidebar-navigation${menuOpen ? ' sidebar-navigation--open' : ''}`} onClick={event => { if (event.target.closest('a')) setMenuOpen(false) }} onKeyDown={event => { if (event.key === 'Escape') { setMenuOpen(false); document.querySelector('.mobile-nav-toggle')?.focus() } }}>
      <nav id="main-navigation" className="social-nav" aria-label="Navegación principal">
        <NavLink to="/" end className="navigation-galaxy-link"><Home size={22} /><span>Mural</span><NavigationGalaxy /></NavLink>
        <NavLink to="/profile" className="navigation-galaxy-link"><UserRound size={22} /><span>Mi perfil</span><NavigationGalaxy /></NavLink>
        <NavLink to="/books" className="navigation-galaxy-link"><NavigationIcon variant="book" /><span>Explorar libros</span><NavigationGalaxy /></NavLink>
        <NavLink to="/events" className="navigation-galaxy-link"><CalendarDays size={22} /><span>Eventos</span><NavigationGalaxy /></NavLink>
        <NavLink to="/recommendations" className="navigation-galaxy-link"><NavigationIcon variant="wand" /><span>Recomendaciones IA</span><NavigationGalaxy /></NavLink>
      </nav>
      <div className="sidebar-account"><Link to="/profile" className="account-link"><span className="avatar">{initials}</span><span>{user.display_name}<small>{roleLabels[user.role]}</small></span></Link><button className="logout-button" onClick={logout}><LogOut size={18} /> Cerrar sesión</button></div>
      </div>
    </aside>
    <div className="social-page-column">
      <header className="social-topbar"><HeaderGreeting displayName={user?.display_name} /><nav className="global-header-actions" aria-label="Accesos del encabezado" onClick={event => { if (event.target.closest('a')) { setMenuOpen(false); if (toolsRef.current) toolsRef.current.open = false } }}>
        <HeaderShortcut to="/messages" label="Mensajes" icon={MessageBubbleIcon} />
        <HeaderShortcut to="/notifications" label="Notificaciones" icon={NotificationBellIcon} />
        {hasTools && <details ref={toolsRef} className="navigation-tools" onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); toolsRef.current.open = false; toolsRef.current.querySelector('summary').focus() } }}>
          <summary className="global-header-action" aria-label="Herramientas"><Settings2 size={21} aria-hidden="true" /><span className="global-header-tooltip" role="tooltip">Herramientas</span></summary>
          <nav className="navigation-tools-menu" aria-label="Herramientas disponibles">
            {groupAccess && <NavLink to="/insights"><BarChart3 size={19} aria-hidden="true" />LibrIA Insights</NavLink>}
            {user.role === 'admin' && <><NavLink to="/admin/profiles"><Settings2 size={19} aria-hidden="true" />Gestionar perfiles</NavLink><NavLink to="/admin/etl"><Database size={19} aria-hidden="true" />Carga de datos</NavLink></>}
          </nav>
        </details>}
      </nav></header>
      <main id="main-content" className="social-main" tabIndex={-1}><Outlet /></main>
    </div>
  </div>
}
