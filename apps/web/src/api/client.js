// Punto único para solicitudes REST. La URL puede cambiar sin tocar las páginas.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

export function apiUrl(path) {
  return `${API_URL}${path}`
}

export async function apiRequest(path, options = {}) {
  const headers = { ...options.headers }
  if (!(options.body instanceof FormData) && !headers['Content-Type']) headers['Content-Type'] = 'application/json'
  const response = await fetch(apiUrl(path), { ...options, headers })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const error = new Error(typeof payload?.detail === 'string' ? payload.detail : 'No fue posible completar la solicitud')
    error.status = response.status
    throw error
  }
  return response.status === 204 ? null : response.json()
}
