// Only community profile URLs may be carried across the authentication flow.
export function profileDestination(search) {
  const candidate = new URLSearchParams(search).get('next') || ''
  return /^\/profiles\/[A-Za-z0-9-]+(?:\?follow=1)?$/.test(candidate) ? candidate : '/'
}

export function rememberProfileDestination(search) {
  const destination = profileDestination(search)
  try {
    if (destination !== '/') sessionStorage.setItem('libria_profile_destination', destination)
    else sessionStorage.removeItem('libria_profile_destination')
  } catch { /* Normal login remains available when session storage is blocked. */ }
}

export function consumeProfileDestination() {
  try {
    const destination = sessionStorage.getItem('libria_profile_destination') || ''
    sessionStorage.removeItem('libria_profile_destination')
    return profileDestination(`next=${encodeURIComponent(destination)}`)
  } catch { return '/' }
}
