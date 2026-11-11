import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiRequest } from '../api/client'
import NotificationBellIcon from './NotificationBellIcon'
import './NotificationShortcut.css'

export default function NotificationShortcut() {
  const { user } = useAuth()
  const location = useLocation()
  const [count, setCount] = useState(0)
  useEffect(() => {
    if (!user) return
    const controller = new AbortController()
    let pending = false
    const refresh = async () => {
      if (pending || controller.signal.aborted) return
      pending = true
      try {
        const result = await apiRequest('/me/notification-inbox?limit=1', { signal: controller.signal, headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
        if (!controller.signal.aborted) setCount(result.unread_count)
      } catch { /* Keep the last confirmed count; the inbox offers retry on errors. */ }
      finally { pending = false }
    }
    setCount(0)
    refresh()
    const timer = setInterval(refresh, 30000)
    window.addEventListener('focus', refresh)
    window.addEventListener('libria-notifications-updated', refresh)
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', refresh); window.removeEventListener('libria-notifications-updated', refresh) }
  }, [user, location.pathname, location.search])
  const label = count ? `Notificaciones: ${count} sin leer` : 'Notificaciones'
  return <NavLink to="/notifications" className="global-header-action notification-shortcut" aria-label={label}>
    <NotificationBellIcon size={21} aria-hidden="true" />
    {count > 0 && <span className="notification-shortcut-count" aria-hidden="true">{count > 99 ? '99+' : count}</span>}
    <span className="global-header-tooltip" role="tooltip">{label}</span>
  </NavLink>
}
