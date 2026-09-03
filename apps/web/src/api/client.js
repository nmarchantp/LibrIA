// Punto único para solicitudes REST. La URL puede cambiar sin tocar las páginas.
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, { headers: { 'Content-Type': 'application/json', ...options.headers }, ...options })
  if (!response.ok) throw new Error('No fue posible completar la solicitud')
  return response.status === 204 ? null : response.json()
}
