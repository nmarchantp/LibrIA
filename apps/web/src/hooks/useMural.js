import { useEffect, useRef, useState } from 'react'
import { feedService } from '../services/feedService'

export default function useMural(userId, audience, category, refresh) {
  const identity = `${userId}:${audience}:${category || 'summary'}:${refresh}`
  const current = useRef(identity)
  current.current = identity
  const [result, setResult] = useState({ identity, loading: true, data: null, error: '', moreError: '', busy: false })
  const moreRequest = useRef(null)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setResult({ identity, loading: true, data: null, error: '', moreError: '', busy: false })
    const request = category ? feedService.page(audience, category, null, controller.signal) : feedService.summary(audience, controller.signal)
    request.then(data => { if (active) setResult({ identity, loading: false, data, error: '', moreError: '', busy: false }) })
      .catch(error => { if (active) setResult({ identity, loading: false, data: null, error: error.message || 'No se pudo cargar el mural.', moreError: '', busy: false }) })
    return () => { active = false; controller.abort(); moreRequest.current?.abort(); moreRequest.current = null }
  }, [identity, audience, category])
  async function loadMore() {
    if (moreRequest.current || !result.data?.next_cursor || result.loading) return
    const controller = new AbortController()
    moreRequest.current = controller
    setResult(value => ({ ...value, busy: true, moreError: '' }))
    try {
      const data = await feedService.page(audience, category, result.data.next_cursor, controller.signal)
      if (current.current !== identity) return
      setResult(value => {
        const seen = new Set(value.data.items.map(item => `${item.feed_item_type}:${item.id}`))
        return { ...value, busy: false, data: { ...data, items: [...value.data.items, ...data.items.filter(item => !seen.has(`${item.feed_item_type}:${item.id}`))] } }
      })
    } catch (error) {
      if (current.current === identity) setResult(value => ({ ...value, busy: false, moreError: error.message || 'No se pudieron cargar más actividades.' }))
    } finally { if (moreRequest.current === controller) moreRequest.current = null }
  }
  return { ...(result.identity === identity ? result : { loading: true, data: null, error: '' }), loadMore }
}
