// Transport only: stable retry identities and optimistic edit versions.
const intents = new Map(), versions = new Map()
const ttl = 10 * 60 * 1000
const basePath = path => path.split('?')[0]
const scoped = (headers, path) => (headers.Authorization || '') + ':' + basePath(path)
const moderatedWrite = (path, method) => method === 'POST'
  ? /^\/(posts|reviews)$/.test(path) || /^\/(?:posts\/[^/]+|activities\/(?:publication|review|reading_event)\/[^/]+)\/comments$/.test(path)
  : method === 'PUT' && (/^\/(posts|reviews)\/[^/]+$/.test(path) || /^\/activities\/(?:publication|review|reading_event)\/[^/]+\/comments\/[^/]+$/.test(path))

async function hash(value) {
  const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : value
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join('')
}
const ordered = value => Array.isArray(value) ? value.map(ordered) : value && typeof value === 'object'
  ? Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])])) : value

async function payloadHash(body) {
  if (body instanceof FormData) {
    const entries = await Promise.all([...body.entries()].map(async ([key, value]) => [key,
      typeof value === 'string' ? value : { name: value.name, type: value.type, digest: await hash(await value.arrayBuffer()) }]))
    return hash(JSON.stringify(entries.sort(([a], [b]) => a.localeCompare(b))))
  }
  try { return hash(JSON.stringify(ordered(JSON.parse(body)))) }
  catch { return hash(String(body ?? '')) }
}

export async function prepareModeratedWrite(path, options, headers) {
  const target = basePath(path), method = options.method?.toUpperCase()
  if (!moderatedWrite(target, method)) return null
  if (method === 'PUT' && headers['If-Match'] == null && versions.has(scoped(headers, target))) {
    headers['If-Match'] = '"' + versions.get(scoped(headers, target)) + '"'
  }
  if (headers['Idempotency-Key']) return null
  const now = Date.now()
  for (const [key, value] of intents) if (now - value.created > ttl) intents.delete(key)
  const key = scoped(headers, target) + ':' + method + ':' + await payloadHash(options.body) + ':' + (headers['If-Match'] || '')
  if (!intents.has(key)) intents.set(key, { id: crypto.randomUUID(), created: now })
  headers['Idempotency-Key'] = intents.get(key).id
  while (intents.size > 128) intents.delete(intents.keys().next().value)
  return { key, id: headers['Idempotency-Key'] }
}

export function finishModeratedWrite(intent, definitive) {
  // Network/5xx outcomes are uncertain: retain the identity for a retry.
  if (intent && definitive && intents.get(intent.key)?.id === intent.id) intents.delete(intent.key)
}

export function rememberModeratedVersions(path, data, headers) {
  const target = basePath(path)
  function remember(item, resource) {
    if (item && Number.isInteger(item.moderation_version) && item.moderation_version > 0) {
      const key = scoped(headers, resource)
      versions.set(key, Math.max(versions.get(key) || 0, item.moderation_version))
    }
  }
  const items = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : data?.id ? [data] : []
  for (const item of items) {
    if (/\/comments$/.test(target)) remember(item, target + '/' + item.id)
    else if (item.feed_item_type !== 'reading_event' && item.id) {
      remember(item, '/' + (item.feed_item_type === 'review' || target.startsWith('/reviews') ? 'reviews' : 'posts') + '/' + item.id)
    }
  }
  if (data?.comment) {
    remember(data.comment, target.endsWith('/' + data.comment.id) ? target : target + '/' + data.comment.id)
  }
  while (versions.size > 256) versions.delete(versions.keys().next().value)
}
