import { apiRequest } from '../api/client'

// Las páginas usarán este servicio y no conocerán detalles de HTTP.
export const authService = {
  login: (credentials) => apiRequest('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  register: (user) => apiRequest('/auth/register', { method: 'POST', body: JSON.stringify(user) }),
  me: (token) => apiRequest('/auth/me', { headers: { Authorization: `Bearer ${token}` } }),
}
