import { useState } from 'react'
import { BookOpen, BrainCircuit, Compass, Home, Library, Menu, Search, X } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

// Estructura compartida por todas las páginas privadas del prototipo.
export default function Layout() {
  const [open, setOpen] = useState(false)
  const links = [{to:'/',label:'Inicio',icon:Home,end:true},{to:'/books',label:'Explorar',icon:Compass},{to:'/library',label:'Mi biblioteca',icon:Library},{to:'/insights',label:'Mis patrones',icon:BrainCircuit}]
  return <div className="app-shell">
    <header className="topbar"><NavLink className="brand" to="/"><span className="brand-icon"><BookOpen size={21}/></span><span>Libr<span>IA</span></span></NavLink>
      <nav className={open ? 'nav nav--open' : 'nav'}>{links.map(({to,label,icon:Icon,end}) => <NavLink key={to} to={to} end={end} onClick={()=>setOpen(false)}><Icon size={17}/>{label}</NavLink>)}</nav>
      <div className="header-actions"><NavLink className="search-trigger" to="/books"><Search size={19}/></NavLink><NavLink className="avatar" to="/profile">NM</NavLink><button className="menu-button" onClick={()=>setOpen(!open)}>{open?<X/>:<Menu/>}</button></div>
    </header>
    <main><Outlet /></main>
    <footer><span className="brand footer-brand">Libr<span>IA</span></span><p>Lee, registra y descubre tu historia como lector.</p><small>Prototipo MVP · Datos demostrativos</small></footer>
  </div>
}
