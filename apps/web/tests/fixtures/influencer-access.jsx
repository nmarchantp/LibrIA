import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '/src/context/AuthContext'
import AccountSettings from '/src/components/AccountSettings'
import AdminProfilesPage from '/src/pages/AdminProfilesPage'
import '/src/styles.css'

const session = { session_id: 'browser-session', inactivity_expires_at: '2099-01-01T00:00:00Z', absolute_expires_at: '2099-01-01T00:00:00Z' }
localStorage.setItem('libria_token', 'isolated-browser-token')
localStorage.setItem('libria_session', JSON.stringify(session))
window.influencerTest = {
  reader: { id: 'reader-one', username: 'reader', display_name: 'Lector de prueba', email: 'reader@example.com', role: 'lector', biography: '', avatar_url: null, email_verified: true },
  requests: [], decisions: [], audits: [], roleHistory: [], actions: [],
}
const realFetch = window.fetch
window.fetch = async (url, options = {}) => {
  const path = String(url)
  if (!path.includes('/api/')) return realFetch(url, options)
  const state = window.influencerTest
  const body = options.body ? JSON.parse(options.body) : null
  let result = {}
  if (path.endsWith('/auth/me') || path.endsWith('/accounts/me')) result = state.reader
  else if (path.endsWith('/auth/session') || path.endsWith('/auth/activity')) result = session
  else if (path.endsWith('/roles/access')) result = { admin: true }
  else if (path.endsWith('/accounts/me/sessions')) result = []
  else if (path.includes('/roles/profiles?')) result = { items: [state.reader], total: 1 }
  else if (path.includes('/accounts/admin?')) result = { items: [], total: 0 }
  else if (path.endsWith('/roles/requests/me') || path.endsWith('/roles/profiles/reader-one/requests')) result = state.requests
  else if (path.endsWith('/roles/profiles/reader-one/history')) result = state.roleHistory
  else if (path.endsWith('/accounts/admin/reader-one/history')) result = state.audits
  else if (path.endsWith('/roles/me/influencer-permissions')) result = { suspended: Boolean(state.reader.influencer_permissions_suspended), until: state.reader.influencer_suspended_until, reason: state.audits[0]?.reason }
  else if (path.endsWith('/roles/requests/pending')) result = state.requests.filter(item => item.status === 'pending')
  else if (path.endsWith('/roles/requests') && options.method === 'POST') {
    result = { ...body, id: `request-${state.requests.length + 1}`, display_name: state.reader.display_name, email: state.reader.email, note: body.motivation, status: 'pending', created_at: new Date().toISOString() }
    state.requests.unshift(result)
  } else if (/\/roles\/requests\/.+\/(approve|reject)$/.test(path)) {
    state.decisions.push(body)
    const identifier = path.split('/').at(-2)
    result = { ...state.requests.find(item => item.id === identifier), status: path.endsWith('/approve') ? 'approved' : 'rejected', decision_reason: body.reason, decided_at: new Date().toISOString(), decided_by_name: 'Administrador de prueba', decided_by_user_id: 'admin-one' }
    state.requests = state.requests.map(item => item.id === identifier ? result : item)
    if (result.status === 'approved') state.reader = { ...state.reader, role: 'influencer' }
  } else if (/\/roles\/profiles\/reader-one\/(influencer-suspension|influencer-resume|revoke)$/.test(path)) {
    const action = path.split('/').at(-1)
    state.actions.push({ action, ...body })
    state.reader = { ...state.reader, influencer_permissions_suspended: action === 'influencer-suspension', influencer_suspended_until: body.until || null, role: action === 'revoke' ? 'lector' : 'influencer' }
    state.audits.unshift({ id: `audit-${state.actions.length}`, actor_user_id: 'admin-one', created_at: new Date().toISOString(), reason: body.reason, after: { influencer_suspended_until: body.until }, action: action === 'influencer-suspension' ? 'influencer_suspended' : action === 'influencer-resume' ? 'influencer_resumed' : 'role_changed' })
    result = state.reader
  }
  return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } })
}
function Fixture() {
  const [mode, setMode] = useState('reader')
  return <MemoryRouter initialEntries={['/settings?section=role']}><AuthProvider>
    <nav>{['reader', 'admin'].map(value => <button key={value} onClick={() => setMode(value)}>{value}</button>)}</nav>
    {mode === 'reader' ? <AccountSettings preferences={{ loading: true }} /> : <AdminProfilesPage />}
  </AuthProvider></MemoryRouter>
}
createRoot(document.getElementById('root')).render(<Fixture />)
