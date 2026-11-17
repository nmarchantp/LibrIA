import { apiRequest } from '../api/client'

export function accountRequest(path, options = {}) {
  return apiRequest(path, { ...options, headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}`, ...options.headers } })
}

let saveQueue = Promise.resolve()
function saveProgress(data) {
  const token = localStorage.getItem('libria_token')
  const request = () => {
    if (token !== localStorage.getItem('libria_token')) throw new Error('La sesión cambió. Recarga tus preferencias.')
    return accountRequest('/profiles/me/onboarding', { method: 'PATCH', body: JSON.stringify(data) })
  }
  const next = saveQueue.then(request, request)
  saveQueue = next.catch(() => {})
  return next
}

export const onboardingService = {
  get: () => accountRequest('/profiles/me/onboarding'),
  syncFavorites: () => accountRequest('/profiles/me/onboarding/library', { method: 'POST' }),
  guide: (step, book_ref) => accountRequest('/profiles/me/onboarding/guide', { method: 'PATCH', body: JSON.stringify({ step, ...(book_ref ? { book_ref } : {}) }) }),
  catalogs: () => apiRequest('/profiles/preference-catalogs'),
  save: saveProgress,
  share: shared => accountRequest('/profiles/me/onboarding/sharing', { method: 'PATCH', body: JSON.stringify({ shared }) }),
  theme: theme => accountRequest('/profiles/me/onboarding/theme', { method: 'PATCH', body: JSON.stringify({ theme }) }),
}
