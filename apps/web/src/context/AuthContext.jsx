import { createContext, useContext, useState } from 'react'
import { authService } from '../services/authService'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const authenticate = async (action, data) => {
    const result = await authService[action](data)
    localStorage.setItem('libria_token', result.access_token)
    setUser(result.user)
    return result
  }
  const value = { user, login: data => authenticate('login', data), register: data => authenticate('register', data) }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('useAuth requiere AuthProvider');return value}
