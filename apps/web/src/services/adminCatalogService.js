import { apiRequest } from '../api/client'

export function adminCatalogRequest(path, { body, method, key, signal } = {}) {
  return apiRequest(`/admin/catalog${path}`, {
    headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}`, ...(key ? { 'Idempotency-Key': key } : {}) },
    signal,
    ...(body !== undefined ? { body: JSON.stringify(body), method: method || 'POST' } : {}),
  })
}

export function catalogChanged() {
  window.dispatchEvent(new Event('libria:book-activity-changed'))
  window.dispatchEvent(new Event('libria:catalog-identity-changed'))
}
