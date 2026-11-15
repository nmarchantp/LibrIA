const loopback = hostname => ['localhost', '127.0.0.1', '[::1]'].includes(hostname)

// A browser on another device must never use that device's loopback for our API.
export function resolveApiLocation(configuredUrl, pageOrigin, development) {
  const url = new URL(configuredUrl || '/api', pageOrigin)
  if (development && loopback(url.hostname)) {
    return new URL(url.pathname, pageOrigin).href.replace(/\/$/, '')
  }
  return url.href.replace(/\/$/, '')
}
