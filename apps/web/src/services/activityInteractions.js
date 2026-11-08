import { apiRequest } from '../api/client'

export const activityKey = item => `${item.feed_item_type}:${item.id}`
const base = item => ({ like_count: item.like_count ?? null, liked_by_me: item.liked_by_me ?? false,
    comment_count: item.comment_count ?? null, view_count: item.view_count ?? null, capabilities: item.capabilities || {}, observed_at: item.observed_at || '', likeBusy: false, error: '' })
const path = item => `/activities/${item.feed_item_type}/${encodeURIComponent(item.id)}`
const request = (item, suffix, method = 'GET', body, signal) => apiRequest(path(item) + suffix, {
  method, headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` },
  ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal,
})

// One scoped store per signed-in mural; components never register a view on mount.
export function createInteractionStore() {
  const entries = new Map(), listeners = new Set()
  const notify = () => listeners.forEach(listener => listener())
  function get(item) {
    const key = activityKey(item)
    if (!entries.has(key)) entries.set(key, { value: base(item), origin: item })
    return entries.get(key).value
  }
  function patch(item, changes) {
    const key = activityKey(item)
    const previous = get(item)
    entries.set(key, { ...entries.get(key), value: { ...previous, ...changes } })
    notify()
  }
  function apply(item, counts) {
    const previous = get(item)
    if (counts.observed_at && previous.observed_at && counts.observed_at < previous.observed_at) return
    patch(item, { ...counts, error: '' })
  }
  return {
    get,
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener) },
    seed(item) {
      get(item)
      const entry = entries.get(activityKey(item))
      if (entry.origin === item) return
      entry.origin = item
      if (!entry.value.likeBusy && item.observed_at && (!entry.value.observed_at || item.observed_at > entry.value.observed_at)) apply(item, base(item))
    },
    async toggleLike(item) {
      const value = get(item)
      if (value.likeBusy || !value.capabilities.can_like) return
      patch(item, { likeBusy: true, error: '' })
      try { apply(item, await request(item, '/like', value.liked_by_me ? 'DELETE' : 'PUT')) }
      catch (error) { patch(item, { error: error.message || 'No se pudo actualizar Me gusta.' }) }
      finally { patch(item, { likeBusy: false }) }
    },
    async view(item, action) {
      try { apply(item, await request(item, '/view', 'PUT', { action })); return true }
      catch (error) { patch(item, { error: error.message || 'No se pudo abrir esta actividad.' }); return false }
    },
    async comments(item,signal) {const revision=get(item).commentRevision||0;const rows=await request(item,'/comments','GET',undefined,signal);if((get(item).commentRevision||0)!==revision)return get(item).commentItems||rows;patch(item,{commentItems:rows});return rows},
    async comment(item, body) {
      const result = await request(item, '/comments', 'POST', { body })
      apply(item, result.interactions)
      const rows=get(item).commentItems
      if(rows)patch(item,{commentItems:[...rows.filter(row=>row.id!==result.comment.id),result.comment],commentRevision:(get(item).commentRevision||0)+1})
      return result.comment
    },
    async updateComment(item,id,body) {
      const result=await request(item,`/comments/${id}`,'PUT',{body})
      apply(item,result.interactions)
      const rows=get(item).commentItems
      if(rows)patch(item,{commentItems:rows.map(row=>row.id===id?result.comment:row),commentRevision:(get(item).commentRevision||0)+1})
      return result.comment
    },
    async deleteComment(item,id) {
      const result=await request(item,`/comments/${id}`,'DELETE')
      apply(item,result.interactions)
      const rows=get(item).commentItems
      if(rows)patch(item,{commentItems:rows.filter(row=>row.id!==id),commentRevision:(get(item).commentRevision||0)+1})
    },
  }
}
