// Punto único para solicitudes REST. La URL puede cambiar sin tocar las páginas.
const configuredUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'
// The local launcher listens on IPv4. Avoid resolving its address to ::1.
const localUrl = new URL(configuredUrl, window.location.origin)
if (import.meta.env.DEV && localUrl.protocol === 'http:' && localUrl.hostname === 'localhost') localUrl.hostname = '127.0.0.1'
export const API_URL = localUrl.href.replace(/\/$/, '')

export function apiUrl(path) {
  return `${API_URL}${path}`
}

export async function apiRequest(path, options = {}) {
  const headers = { ...options.headers }
  if (options.body != null && !(options.body instanceof FormData) && !headers['Content-Type']) headers['Content-Type'] = 'application/json'
  let response
  try {
    response = await fetch(apiUrl(path), { ...options, headers })
  } catch (cause) {
    if (cause.name === 'AbortError') throw cause
    const error = new Error('No se pudo conectar con LibrIAverse. Comprueba que el backend esté iniciado y accesible.')
    error.code = 'backend_connection'
    throw error
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const error = new Error(typeof payload?.detail === 'string' ? payload.detail : payload?.detail?.message || 'No fue posible completar la solicitud')
    error.code = payload?.detail?.code
    error.status = response.status
    throw error
  }
  const data = response.status === 204 ? null : await response.json()
  if (/^\/(reviews|readings)(\/|\?|$)/.test(path) && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method?.toUpperCase())) {
    window.dispatchEvent(new Event('libria:book-activity-changed'))
  }
  return data
}
