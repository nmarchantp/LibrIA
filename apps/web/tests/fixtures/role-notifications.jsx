import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '/src/context/AuthContext'
import NotificationShortcut from '/src/components/NotificationShortcut'
import NotificationsPage from '/src/pages/NotificationsPage'
import '/src/styles.css'

localStorage.setItem('libria_token', 'isolated-notification-test')
localStorage.setItem('libria_session', JSON.stringify({ session_id: 'fixture', inactivity_expires_at: '2099-01-01T00:00:00Z', absolute_expires_at: '2099-01-01T00:00:00Z' }))
window.noticeTest = { mode: 'admin', read: new Set(), requests: [] }
const realFetch = window.fetch
window.fetch = async (url, options = {}) => {
  const path = String(url), state = window.noticeTest
  if (!path.includes('/api/')) return realFetch(url, options)
  let result = {}
  if (path.endsWith('/auth/me')) result = { id: state.mode, display_name: state.mode, role: state.mode === 'admin' ? 'admin' : 'lector' }
  else if (path.endsWith('/roles/access')) result = { admin: state.mode === 'admin' }
  else if (path.endsWith('/read')) {
    const id = path.split('/').at(-2)
    state.read.add(id); result = { id, read_at: new Date().toISOString() }
  } else if (path.includes('/me/notification-inbox')) {
    const id = state.mode === 'admin' ? 'requested-one' : 'rejected-one'
    const item = { id, source: 'role', kind: state.mode === 'admin' ? 'requested' : 'rejected', message: state.mode === 'admin' ? 'Camila solicitó el perfil influencer' : 'Tu solicitud de perfil influencer fue rechazada', href: state.mode === 'admin' ? '/admin/profiles?tab=requests' : '/settings', decision_reason: state.mode === 'admin' ? null : 'Falta evidencia pública de actividad literaria.', created_at: new Date().toISOString(), read_at: state.read.has(id) ? new Date().toISOString() : null }
    result = { items: [item], has_more: false, unread_count: item.read_at ? 0 : 1 }
    state.requests.push(path)
  }
  return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } })
}
function Fixture() {
  const [mode, setMode] = useState('admin')
  return <MemoryRouter><nav>{['admin', 'lector'].map(value => <button key={value} onClick={() => { window.noticeTest.mode = value; setMode(value) }}>{value}</button>)}</nav>
    <AuthProvider key={mode}><NotificationShortcut /><NotificationsPage /></AuthProvider>
  </MemoryRouter>
}
createRoot(document.getElementById('root')).render(<Fixture />)
