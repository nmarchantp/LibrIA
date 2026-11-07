import { BookOpen, CalendarDays, Database, Home, LogOut, Settings2, UserRound, BarChart3, Menu, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { apiRequest } from '../api/client'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import BrandLogo from './BrandLogo'
import NavigationIcon from './NavigationIcon'
import NavigationGalaxy from './NavigationGalaxy'
import MessageBubbleIcon from './MessageBubbleIcon'
import NotificationBellIcon from './NotificationBellIcon'
import HeaderGreeting from './HeaderGreeting'
import MagicalBackground from './MagicalBackground'
import './LayoutNavigation.css'


const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', admin: 'Administrador' }

function HeaderShortcut({ to, label, icon: Icon }) {
  const tooltipId = useId()
  return <NavLink to={to} className="global-header-action" aria-label={label} aria-describedby={tooltipId}>
    <Icon size={21} aria-hidden="true" /><span id={tooltipId} className="global-header-tooltip" role="tooltip">{label}</span>
  </NavLink>
}

export default function Layout() {
  const { user, access, logout } = useAuth()
  const { magicalBackground, magicalBackgroundMotion } = useTheme()
  const [groupAccess, setGroupAccess] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width:700px)').matches)
  const drawerRef = useRef(null)
  const toggleRef = useRef(null)
  const closeRef = useRef(null)
  const pageRef = useRef(null)
  useEffect(() => {
    const query = window.matchMedia('(max-width:700px)')
    const update = () => { setMobile(query.matches); setMenuOpen(false) }
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    if (!mobile || !menuOpen) return
    const bodyOverflow = document.body.style.overflow
    const rootOverflow = document.documentElement.style.overflow
    document.body.style.overflow = 'hidden'
    document.documentElement.style.overflow = 'hidden'
    const background = [pageRef.current, toggleRef.current, document.querySelector('.social-sidebar > .brand-link'), document.querySelector('.skip-link')].filter(Boolean)
    const previousInert = background.map(node => node.inert)
    background.forEach(node => { node.inert = true })
    // Wait for visibility and inert changes before moving keyboard focus.
    let focusFrame = requestAnimationFrame(() => {
      focusFrame = requestAnimationFrame(() => closeRef.current?.focus({ preventScroll: true }))
    })
    const focusable = () => [...drawerRef.current.querySelectorAll('a[href],button:not(:disabled),[tabindex="0"]')].filter(node => node.getClientRects().length)
    const onKey = event => {
      if (event.key === 'Escape') { event.preventDefault(); setMenuOpen(false) }
      if (event.key !== 'Tab') return
      const items = focusable(), first = items[0], last = items.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    const onFocus = event => { if (!drawerRef.current?.contains(event.target)) closeRef.current?.focus() }
    document.addEventListener('keydown', onKey)
    document.addEventListener('focusin', onFocus)
    return () => {
      cancelAnimationFrame(focusFrame)
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('focusin', onFocus)
      document.body.style.overflow = bodyOverflow
      document.documentElement.style.overflow = rootOverflow
      background.forEach((node, index) => { node.inert = previousInert[index] })
      if (window.matchMedia('(max-width:700px)').matches) toggleRef.current?.focus({ preventScroll: true })
    }
  }, [mobile, menuOpen])
  const [headerScrolled, setHeaderScrolled] = useState(() => window.scrollY > 8)
  const toolsRef = useRef(null)
  const { pathname, search } = useLocation()
  const hasTools = groupAccess || access?.admin
  useEffect(() => {
    const updateHeader = () => setHeaderScrolled(window.scrollY > 8)
    updateHeader()
    window.addEventListener('scroll', updateHeader, { passive: true })
    return () => window.removeEventListener('scroll', updateHeader)
  }, [])
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
    <aside className={`social-sidebar${menuOpen ? ' mobile-menu-open' : ''}`}>
      <Link className="brand-link" to="/" aria-label="LibrIAverse, tu universo literario. Ir al mural"><BrandLogo /></Link>
      <button className={`mobile-nav-backdrop${menuOpen ? ' mobile-nav-backdrop--open' : ''}`} type="button" aria-label="Cerrar menú principal" tabIndex={-1} aria-hidden="true" onClick={() => setMenuOpen(false)} />
      <div ref={drawerRef} id="sidebar-navigation" className={`sidebar-navigation${menuOpen ? ' sidebar-navigation--open' : ''}`} role={mobile ? 'dialog' : undefined} aria-modal={mobile && menuOpen ? true : undefined} aria-label={mobile ? 'Menú principal' : undefined} aria-hidden={mobile && !menuOpen ? true : undefined} inert={mobile && !menuOpen ? true : undefined} onClick={event => { if (event.target.closest('a')) setMenuOpen(false) }}>
      <div className="mobile-drawer-heading"><span>Menú principal</span><button ref={closeRef} type="button" aria-label="Cerrar menú principal" onClick={() => setMenuOpen(false)}><X size={22} aria-hidden="true" /></button></div>
      <nav id="main-navigation" className="social-nav" aria-label="Navegación principal">
        <NavLink to="/" end className="navigation-galaxy-link"><Home size={22} /><span>Mural</span><NavigationGalaxy /></NavLink>
        <NavLink to="/profile" className="navigation-galaxy-link"><UserRound size={22} /><span>Mi perfil</span><NavigationGalaxy /></NavLink>
        <NavLink to="/books" className="navigation-galaxy-link"><NavigationIcon variant="book" /><span>Explorar libros</span><NavigationGalaxy /></NavLink>
        <NavLink to="/events" className="navigation-galaxy-link"><CalendarDays size={22} /><span>Eventos</span><NavigationGalaxy /></NavLink>
        <NavLink to="/recommendations" className="navigation-galaxy-link"><NavigationIcon variant="wand" /><span>Recomendaciones IA</span><NavigationGalaxy /></NavLink>
        <NavLink to="/settings" className="navigation-galaxy-link"><Settings2 size={22} /><span>Configuración</span><NavigationGalaxy /></NavLink>
      </nav>
      <div className="sidebar-account"><Link to="/profile" className="account-link"><span className="avatar">{initials}</span><span>{user.display_name}<small>{roleLabels[user.role]}</small></span></Link><button className="logout-button" onClick={logout}><LogOut size={18} /> Cerrar sesión</button></div>
      </div>
    </aside>
    <div ref={pageRef} className="social-page-column" data-magical-background={magicalBackground ? 'enabled' : undefined} data-starfield-motion={magicalBackgroundMotion ? 'enabled' : 'disabled'}>
      {magicalBackground && <MagicalBackground motionEnabled={magicalBackgroundMotion} />}
      <header className={`social-topbar${headerScrolled ? ' is-scrolled' : ''}`}><HeaderGreeting displayName={user?.display_name} /><nav className="global-header-actions" aria-label="Accesos del encabezado" onClick={event => { if (event.target.closest('a')) { setMenuOpen(false); if (toolsRef.current) toolsRef.current.open = false } }}>
        <HeaderShortcut to="/messages" label="Mensajes" icon={MessageBubbleIcon} />
        <HeaderShortcut to="/notifications" label="Notificaciones" icon={NotificationBellIcon} />
        {hasTools && <details ref={toolsRef} className="navigation-tools" onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); toolsRef.current.open = false; toolsRef.current.querySelector('summary').focus() } }}>
          <summary className="global-header-action" aria-label="Herramientas"><Settings2 size={21} aria-hidden="true" /><span className="global-header-tooltip" role="tooltip">Herramientas</span></summary>
          <nav className="navigation-tools-menu" aria-label="Herramientas disponibles">
            {groupAccess && <NavLink to="/insights"><BarChart3 size={19} aria-hidden="true" />LibrIA Insights</NavLink>}
            {access?.admin && <><NavLink to="/admin/profiles"><Settings2 size={19} aria-hidden="true" />Gestionar perfiles</NavLink><NavLink to="/admin/environment"><Settings2 size={19} aria-hidden="true" />Configurar aplicación</NavLink><NavLink to="/admin/etl"><Database size={19} aria-hidden="true" />Carga de datos</NavLink></>}
            {access?.catalog_preview && <NavLink to="/admin/catalog"><BookOpen size={19} aria-hidden="true" />Gestionar libros</NavLink>}
          </nav>
        </details>}
      <button ref={toggleRef} className="mobile-nav-toggle" type="button" aria-label={menuOpen ? 'Cerrar menú principal' : 'Abrir menú principal'} aria-expanded={menuOpen} aria-controls="sidebar-navigation" onClick={() => setMenuOpen(open => !open)}>{menuOpen ? <X size={22} /> : <Menu size={22} />}<span>{menuOpen ? 'Cerrar' : 'Menú'}</span></button>
      </nav></header>
      <main id="main-content" className="social-main" tabIndex={-1}><Outlet /></main>
    </div>
  </div>
}
