import { apiRequest } from '../api/client'

// Las páginas usarán este servicio y no conocerán detalles de HTTP.
export const authService = {
  login: (credentials) => apiRequest('/auth/login', { method: 'POST', credentials: 'include', body: JSON.stringify(credentials) }),
  register: (user) => apiRequest('/auth/register', { method: 'POST', credentials: 'include', body: JSON.stringify(user) }),
  google: () => apiRequest('/auth/google/session', { method: 'POST', credentials: 'include' }),
  me: (token) => apiRequest('/auth/me', { headers: { Authorization: `Bearer ${token}` } }),
  refresh: () => apiRequest('/auth/refresh', { method: 'POST', credentials: 'include' }),
  session: (token) => apiRequest('/auth/session', { headers: { Authorization: `Bearer ${token}` } }),
  activity: (token) => apiRequest('/auth/activity', { method: 'POST', headers: { Authorization: `Bearer ${token}` } }),
  logout: (token) => apiRequest('/auth/logout', { method: 'POST', credentials: 'include', headers: { Authorization: `Bearer ${token}` } }),
}
