import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '../../src/context/AuthContext'
import AccountManagement from '../../src/components/AccountManagement'
import AdminAccountManagement from '../../src/components/AdminAccountManagement'
import RecoverAccountPage from '../../src/pages/RecoverAccountPage'
import '../../src/styles.css'
import '../../src/pages/AccountPage.css'

const id = '00000000-0000-4000-8000-000000000001'
let account = { id, username: 'reader_test', display_name: 'Lector de prueba', email: 'reader@example.com', role: 'lector', biography: 'Historia guardada', avatar_url: null, account_status: 'active', suspended: false, google_linked: true, email_verified: true }
const session = { session_id: '00000000-0000-4000-8000-000000000002', inactivity_expires_at: new Date(Date.now()+3600000).toISOString(), absolute_expires_at: new Date(Date.now()+7200000).toISOString() }
window.accountTest = { calls: [], failPassword: false }
window.fetch = async (input, options = {}) => {
  const url = new URL(input, location.href)
  const path = url.pathname.replace(/^\/api/, '')
  const method = options.method || 'GET'
  const body = typeof options.body === 'string' ? JSON.parse(options.body) : null
  window.accountTest.calls.push({ path, method, body })
  const result = (value, status = 200) => new Response(status === 204 ? null : JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
  if (path === '/auth/refresh') return result({ ...session, user: account, access_token: 'test-token' })
  if (path === '/auth/me') return result(account)
  if (path === '/roles/access') return result({ admin: true })
  if (path === '/auth/session' || path === '/auth/activity') return result(session)
  if (path === '/auth/logout') return result(null, 204)
  if (path === '/accounts/me') { if (method === 'PATCH') account = { ...account, ...body }; return result(account) }
  if (path === '/accounts/me/sessions') return result([{ id: session.session_id, last_activity_at: new Date().toISOString() }])
  if (path === '/accounts/me/password') return window.accountTest.failPassword ? result({ detail: 'No fue posible verificar tu identidad' }, 400) : result(null, 204)
  if (path === '/accounts/admin') return result({ items: [account], total: 1 })
  if (path.endsWith('/history')) return result([{ id: 'audit-1', action: 'profile_updated', created_at: new Date().toISOString(), before: {}, after: {}, correlation_id: 'correlation-test' }])
  if (path.endsWith('/suspension')) { account = { ...account, suspended: body.suspended }; return result(account) }
  if (path === '/accounts/recovery/request') return result({ status: 'sent' })
  if (path === '/accounts/recovery/deletion') return result({ status: 'recovered', suspended: true })
  if (path === '/accounts/recovery/password') return result(null, 204)
  return result({ detail: 'Unexpected test endpoint: ' + path }, 404)
}
const recovery = new URLSearchParams(location.search).has('recovery')
createRoot(document.getElementById('root')).render(<BrowserRouter>{recovery ? <RecoverAccountPage /> : <AuthProvider><AccountManagement /><AdminAccountManagement /></AuthProvider>}</BrowserRouter>)
