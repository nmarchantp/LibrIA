import { createRoot } from 'react-dom/client'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '/src/context/AuthContext'
import { authService } from '/src/services/authService'
import AdminGate from '/src/components/AdminGate'
import SessionGate from '/src/components/SessionGate'
import AdminCatalogPage from '/src/pages/AdminCatalogPage'
import { applyTheme } from '/src/theme/themes'
import '/src/styles.css'
import '/src/theme/themes.css'

applyTheme('lavanda')
localStorage.setItem('libria_token', 'isolated-maintenance-test')
authService.me = async () => ({ id: 'fixture-admin', role: 'lector' })
const edition = (id, title) => ({ id, title, language: 'es', isbn13: id === 'edition-a' ? '9780306406157' : '9780140328721', isbn10: '',
  page_count: 300, publisher_name: 'Editorial de prueba', publication_date: '2024', cover_url: null, sources: [{ provider: 'google-books', external_id: id }] })
const makeBook = (id, title) => ({ id, title, authors: ['Sarah J. Maas'], description: 'Una sinopsis de prueba.', categories: ['Fantasía'],
  series_title: '', volume_number: '', edition_count: 1, isbn_count: 1, cover_url: null, duplicate_count: 1, version: 'version-1',
  editions: [edition('edition-' + id, title)], changes: [], members: [], possible_duplicates: [] })
const books = { a: makeBook('a', 'Una corte de rosas y espinas'), b: makeBook('b', 'Una corte de rosas y espinas (NE)') }
books.a.possible_duplicates = [{ ...books.b, possible_duplicates: [] }]
window.maintenanceTest = { calls: [], books, fail: false }
let revision = 1
window.fetch = async (url, options = {}) => {
  const parsed = new URL(url, location.origin)
  const path = parsed.pathname.split('/api').pop()
  const method = options.method || 'GET'
  const body = options.body ? JSON.parse(options.body) : null
  window.maintenanceTest.calls.push({ path, method, body })
  let payload, status = 200
  const rows = Object.values(books)
  const side = id => ({ canonical_id: id, works: [{ id, title: books[id].title }], authors: books[id].authors.map(name => ({ name })),
    editions: books[id].editions, sources: [], references: [] })
  if (path === '/roles/access') payload = { admin: true, catalog_preview: true, catalog_merge: true, catalog_manage: true }
  else if (window.maintenanceTest.fail) { status = 503; payload = { detail: 'Error de prueba recuperable' } }
  else if (path === '/admin/catalog/inventory') {
    const query = parsed.searchParams.get('q')?.toLowerCase() || ''
    const items = rows.filter(book => [book.title, ...book.authors].some(value => value.toLowerCase().includes(query)))
    payload = { items, total: items.length, stats: { works: rows.length, editions: rows.reduce((sum, book) => sum + book.editions.length, 0), possible_duplicates: rows.length > 1 ? rows.length : 0 } }
  } else if (path === '/admin/catalog/works' && method === 'GET') payload = rows
  else if (path === '/admin/catalog/works' && method === 'POST') {
    books.manual = { ...makeBook('manual', body.title), ...body, editions: [], edition_count: 0, isbn_count: 0, duplicate_count: 0, version: 'version-' + ++revision }
    payload = books.manual
  } else if (/\/works\/[^/]+\/editions$/.test(path) && method === 'POST') {
    const id = path.split('/')[4]
    books[id].editions.push({ id: 'edition-manual', ...body, isbn13: body.isbn, sources: [{ provider: 'libria-feed' }] })
    books[id].edition_count++
    books[id].version = 'version-' + ++revision
    payload = books[id]
  }
  else if (/\/works\/[^/]+$/.test(path)) {
    const id = path.split('/').pop()
    if (method === 'PATCH') {
      Object.assign(books[id], body, { version: 'version-' + ++revision })
      books[id].changes.unshift({ action: 'work_update', reason: body.reason, created_at: new Date().toISOString() })
    }
    payload = books[id]
  } else if (/\/editions\/[^/]+$/.test(path) && method === 'PATCH') {
    const id = path.split('/')[4]
    const selected = books[id].editions.find(row => row.id === path.split('/').pop())
    Object.assign(selected, body)
    books[id].version = 'version-' + ++revision
    payload = books[id]
  } else if (path === '/admin/catalog/merge-previews') {
    window.maintenanceTest.merge = body
    payload = { source: side(body.source_work_id), target: side(body.target_work_id), conflicts: [], evidence: {},
      impact: { editions: 2, reading_attempts: 2, reviews: 1 }, decisions: [], preview_id: 'preview-fixture', expires_at: '2099-01-01', fingerprint: 'fixture' }
  } else if (path === '/admin/catalog/merge-previews/preview-fixture/execute') {
    const { source_work_id: source, target_work_id: target } = window.maintenanceTest.merge
    books[target].editions.push(...books[source].editions)
    books[target].edition_count = books[target].editions.length
    books[target].duplicate_count = 0
    delete books[source]
    payload = { operation_id: 'operation-fixture', status: 'merged' }
  } else if (path === '/admin/catalog/history') payload = []
  else { status = 404; payload = { detail: 'Ruta de prueba sin simular: ' + path } }
  return new Response(JSON.stringify(payload), { status, headers: { 'Content-Type': 'application/json' } })
}
createRoot(document.getElementById('root')).render(<AuthProvider><MemoryRouter initialEntries={['/admin/catalog']}><Routes>
  <Route element={<SessionGate />}><Route element={<AdminGate />}><Route path="/admin/catalog" element={<AdminCatalogPage />} /></Route></Route>
  <Route path="/" element={<p>Acceso denegado</p>} />
</Routes></MemoryRouter></AuthProvider>)
