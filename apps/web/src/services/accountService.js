import { apiRequest } from '../api/client'

export function accountRequest(path, method = 'GET', body) {
  return apiRequest(`/accounts${path}`, {
    method,
    headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` },
    ...(body === undefined ? {} : { body: body instanceof FormData ? body : JSON.stringify(body) }),
  })
}
