import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { configureAuthSession } from '../api/client'
import { authService } from '../services/authService'
import { apiRequest } from '../api/client'

const AuthContext = createContext(null)
const TOKEN_KEY = 'libria_token'
const SESSION_KEY = 'libria_session'
const SIGNAL_KEY = 'libria_session_signal'
const WARNING_MS = 5 * 60 * 1000
const CLIENT_ACTIVITY_THROTTLE_MS = 60 * 1000

function storedSession() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null') }
  catch { return null }
}

function saveResult(result) {
  localStorage.setItem(TOKEN_KEY, result.access_token)
  const session = { session_id: result.session_id, inactivity_expires_at: result.inactivity_expires_at,
    absolute_expires_at: result.absolute_expires_at }
  localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  return session
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [access, setAccess] = useState({ admin: false, catalog_preview: false })
  const [accessLoading, setAccessLoading] = useState(true)
  const [accessUser, setAccessUser] = useState(null)
  useEffect(() => {
    let active = true
    setAccess({ admin: false, catalog_preview: false })
    setAccessLoading(Boolean(user))
    if (user) apiRequest('/roles/access', { headers: { Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}` } })
      .then(value => { if (active) setAccess(value) }).catch(() => {})
      .finally(() => { if (active) { setAccessUser(user.id); setAccessLoading(false) } })
    return () => { active = false }
  }, [user])
  const [session, setSession] = useState(storedSession)
  const [loading, setLoading] = useState(true)
  const [sessionError, setSessionError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [now, setNow] = useState(Date.now())
  const [unsavedChanges, setUnsavedChanges] = useState(false)
  const refreshPromise = useRef(null)
  const lastActivitySent = useRef(0)
  const channel = useRef(null)
  const unsavedSources = useRef(new Set())

  const publish = useCallback((type, payload = {}) => {
    const message = { type, payload, at: Date.now() }
    channel.current?.postMessage(message)
    localStorage.setItem(SIGNAL_KEY, JSON.stringify(message))
  }, [])

  const clearLocalSession = useCallback((broadcast = true) => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(SESSION_KEY)
    setUser(null)
    setSession(null)
    setSessionError(false)
    if (broadcast) publish('logout')
  }, [publish])

  const applyResult = useCallback((result, broadcast = true) => {
    const next = saveResult(result)
    setUser(result.user)
    setSession(next)
    setSessionError(false)
    if (broadcast) publish('session', { ...next, user: result.user })
    return result.access_token
  }, [publish])

  const refresh = useCallback(async () => {
    if (refreshPromise.current) return refreshPromise.current
    const run = async () => applyResult(await authService.refresh())
    const coordinated = async () => {
      if (!navigator.locks) return run()
      return navigator.locks.request('libria-session-refresh', async () => {
        const candidate = localStorage.getItem(TOKEN_KEY)
        if (candidate) {
          try {
            const encoded = candidate.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
            const expiry = JSON.parse(atob(encoded)).exp * 1000
            if (expiry - Date.now() > 60_000) return candidate
          } catch { /* malformed tokens are handled by the server */ }
        }
        return run()
      })
    }
    refreshPromise.current = coordinated().finally(() => { refreshPromise.current = null })
    return refreshPromise.current
  }, [applyResult])

  useEffect(() => configureAuthSession({ refresh, unauthorized: () => clearLocalSession() }), [refresh, clearLocalSession])

  useEffect(() => {
    let active = true
    const recover = async () => {
      setLoading(true); setSessionError(false)
      try {
        let token = localStorage.getItem(TOKEN_KEY)
        if (!token) token = await refresh()
        const current = await authService.me(token)
        if (active) setUser(current)
      } catch (error) {
        if (!active) return
        if (error.status === 401 || error.status === 403) clearLocalSession()
        else setSessionError(true)
      } finally { if (active) setLoading(false) }
    }
    recover()
    return () => { active = false }
  }, [attempt, refresh, clearLocalSession])

  useEffect(() => {
    channel.current = typeof BroadcastChannel === 'function' ? new BroadcastChannel('libria-session') : null
    const receive = event => {
      const message = event.data
      if (message?.type === 'logout') clearLocalSession(false)
      if (message?.type === 'session' && message.payload?.user) {
        setUser(message.payload.user); setSession(message.payload); setSessionError(false)
      }
    }
    channel.current?.addEventListener('message', receive)
    const storage = event => {
      if (event.key !== SIGNAL_KEY || !event.newValue) return
      try { receive({ data: JSON.parse(event.newValue) }) } catch { /* ignore invalid cross-tab data */ }
    }
    window.addEventListener('storage', storage)
    return () => { channel.current?.close(); window.removeEventListener('storage', storage) }
  }, [clearLocalSession])

  const verifySession = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token || !user) return
    try {
      const current = await authService.session(token)
      setSession(previous => ({ ...previous, ...current }))
    } catch (error) {
      if (error.status === 401) clearLocalSession()
    }
  }, [user, clearLocalSession])

  const sendActivity = useCallback(async () => {
    if (!user || Date.now() - lastActivitySent.current < CLIENT_ACTIVITY_THROTTLE_MS) return
    if (session?.inactivity_expires_at && Date.now() >= Date.parse(session.inactivity_expires_at)) {
      clearLocalSession(); return
    }
    lastActivitySent.current = Date.now()
    try {
      const current = await authService.activity(localStorage.getItem(TOKEN_KEY))
      const next = { ...session, ...current }
      setSession(next)
      localStorage.setItem(SESSION_KEY, JSON.stringify(next))
      publish('session', { ...next, user })
    } catch (error) {
      if (error.status === 401) clearLocalSession()
    }
  }, [user, session, clearLocalSession, publish])

  useEffect(() => {
    const activity = event => { if (event.isTrusted) sendActivity() }
    const visibility = () => { if (document.visibilityState === 'visible') verifySession() }
    const unsaved = event => {
      const detail = event.detail || {}
      if (detail.dirty) unsavedSources.current.add(detail.id)
      else unsavedSources.current.delete(detail.id)
      setUnsavedChanges(unsavedSources.current.size > 0)
    }
    for (const type of ['pointerdown', 'touchstart', 'keydown', 'submit']) window.addEventListener(type, activity, true)
    window.addEventListener('focus', verifySession)
    document.addEventListener('visibilitychange', visibility)
    window.addEventListener('libria:unsaved-changes', unsaved)
    return () => {
      for (const type of ['pointerdown', 'touchstart', 'keydown', 'submit']) window.removeEventListener(type, activity, true)
      window.removeEventListener('focus', verifySession)
      document.removeEventListener('visibilitychange', visibility)
      window.removeEventListener('libria:unsaved-changes', unsaved)
    }
  }, [sendActivity, verifySession])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    if (session?.inactivity_expires_at && now >= Date.parse(session.inactivity_expires_at)) clearLocalSession()
  }, [now, session, clearLocalSession])

  const authenticate = async (action, data) => applyResult(await authService[action](data))
  const logout = async () => {
    if (unsavedChanges && !window.confirm('Tienes una reseña, nota o teoría sin guardar. ¿Cerrar sesión y descartar esos cambios?')) return
    const token = localStorage.getItem(TOKEN_KEY)
    try { if (token) await authService.logout(token) } catch { /* local cleanup is still mandatory */ }
    clearLocalSession()
  }
  const expiresAt = session?.inactivity_expires_at ? Date.parse(session.inactivity_expires_at) : 0
  const warning = user && expiresAt > now && expiresAt - now <= WARNING_MS
  const value = { user, access, accessLoading: Boolean(user) && (accessLoading || accessUser !== user.id), loading, sessionError, session, retry: () => setAttempt(current => current + 1), logout,
    endSession: clearLocalSession,
    login: data => authenticate('login', data), register: data => authenticate('register', data),
    googleLogin: () => authenticate('google') }
  return <AuthContext.Provider value={value}>
    {children}
    {warning && <aside className="session-expiry-warning" role="alert">
      <strong>Tu sesión está por vencer</strong>
      <span>Se cerrará por inactividad en menos de 5 minutos.{unsavedChanges ? ' Tienes cambios sin guardar.' : ''}</span>
      <button className="button" type="button" onClick={sendActivity}>Continuar sesión</button>
    </aside>}
  </AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('useAuth requiere AuthProvider');return value}
