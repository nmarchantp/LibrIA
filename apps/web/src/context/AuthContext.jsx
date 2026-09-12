import { createContext, useContext, useEffect, useState } from 'react'
import { authService } from '../services/authService'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sessionError, setSessionError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    const token = localStorage.getItem('libria_token')
    if (!token) { setLoading(false); return }
    setLoading(true)
    setSessionError(false)
    authService.me(token).then(current => { if (active) setUser(current) }).catch(error => {
      if (!active) return
      if (error.status === 401 || error.status === 403) localStorage.removeItem('libria_token')
      else setSessionError(true)
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [attempt])
  const authenticate = async (action, data) => {
    const result = await authService[action](data)
    localStorage.setItem('libria_token', result.access_token)
    setUser(result.user)
    return result
  }
  const logout = () => { localStorage.removeItem('libria_token'); setUser(null); setSessionError(false) }
  const value = { user, loading, sessionError, retry: () => setAttempt(current => current + 1), logout, login: data => authenticate('login', data), register: data => authenticate('register', data) }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('useAuth requiere AuthProvider');return value}
