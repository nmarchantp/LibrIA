import { apiRequest } from '../api/client'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
export const profileService = {
  mine: () => apiRequest('/profiles/me/literary-preferences', { headers: headers() }),
  community: id => apiRequest(`/profiles/${encodeURIComponent(id)}`, { headers: headers() }),
  catalogs: () => apiRequest('/profiles/preference-catalogs', { headers: headers() }),
  readingGenres: () => apiRequest('/profiles/me/reading-genres', { headers: headers() }),
  save: fields => apiRequest('/profiles/me/literary-preferences', { method: 'PATCH', headers: headers(), body: JSON.stringify(fields) }),
}
