// Isolated browser fixture. Never calls or writes to the real backend.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import BooksPage from '/src/pages/BooksPage'
import '/src/styles.css'
import '/src/theme/themes.css'

window.searchQA = { requests: [], aborted: 0, delay: 20, networkError: false }
const qa = window.searchQA
const realFetch = window.fetch
window.fetch = (url, options = {}) => {
  if (!String(url).includes('/api/')) return realFetch(url, options)
  const parsed = new URL(url, location.href)
  qa.requests.push({ query: parsed.searchParams.get('q'), refresh: parsed.searchParams.get('refresh'), start: parsed.searchParams.get('start_index'), provider: parsed.searchParams.get('provider'), page: parsed.searchParams.get('page') })
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); qa.aborted++; reject(new DOMException('Aborted', 'AbortError')) }
    const timer = setTimeout(() => {
      options.signal?.removeEventListener('abort', abort)
      if (qa.networkError) { reject(new TypeError('Simulated unavailable backend')); return }
      const page = parsed.searchParams.get('provider') === 'open_library' ? Number(parsed.searchParams.get('page') || 1) : Number(parsed.searchParams.get('start_index') || 0)
      const query = parsed.searchParams.get('q')
      const item = { id: `${query}-${page}`, volumeInfo: { title: `${query} ${page}`, authors: [null, 'Author'], industryIdentifiers: [null], imageLinks: { thumbnail: 42 } } }
      resolve(new Response(JSON.stringify(qa.rawResult || { items: query === 'empty' ? null : [null, {}, item], has_more: page === 0 && query !== 'empty', next_start_index: qa.openLibrary ? null : 40,
        ...(qa.openLibrary ? { active_provider: 'open_library', next_page: 2 } : {}) }), { headers: { 'Content-Type': 'application/json' } }))
    }, qa.delay)
    if (options.signal?.aborted) abort()
    else options.signal?.addEventListener('abort', abort, { once: true })
  })
}
createRoot(document.getElementById('root')).render(<StrictMode><MemoryRouter><BooksPage /></MemoryRouter></StrictMode>)
