// Punto único para solicitudes REST. La URL puede cambiar sin tocar las páginas.
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } })
  if (!response.ok) {
    const error = new Error('No fue posible completar la solicitud')
    error.status = response.status
    throw error
  }
  return response.status === 204 ? null : response.json()
}
