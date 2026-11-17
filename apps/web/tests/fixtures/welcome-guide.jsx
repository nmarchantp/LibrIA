import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Navigate, Route, Routes, useSearchParams } from 'react-router-dom'
import { AuthProvider } from '../../src/context/AuthContext'
import { LibraryProvider } from '../../src/context/LibraryContext'
import { ThemeProvider } from '../../src/context/ThemeContext'
import WelcomeGuide from '../../src/components/WelcomeGuide'
import InitialLiteraryDNA from '../../src/components/InitialLiteraryDNA'
import InsightsPage from '../../src/pages/InsightsPage'
import BooksPage from '../../src/pages/BooksPage'
import BookDetailPage from '../../src/pages/BookDetailPage'
import LibraryPage from '../../src/pages/LibraryPage'
import LibraryBookPage from '../../src/pages/LibraryBookPage'
import { registrationBooks } from './registration-books'
import '../../src/styles.css'
import '../../src/theme/themes.css'

const user = { id: 'guide-reader', role: 'lector', display_name: 'Lectora de prueba', email: 'guide@example.com', onboarding_required: false }
const session = { session_id: 'guide-session', inactivity_expires_at: '2099-01-01T00:00:00Z', absolute_expires_at: '2099-01-01T00:00:00Z' }
const stored = key => JSON.parse(sessionStorage.getItem(key) || 'null')
let guide = stored('guide-test-progress') || { version: 1, step: 'analysis' }
let readings = stored('guide-test-readings') || []
localStorage.setItem('libria_token', 'guide-test-token')
localStorage.setItem('libria_session', JSON.stringify(session))
window.welcomeTest = { calls: [] }
window.fetch = async (input, options = {}) => {
  const url = new URL(input, location.href)
  const path = url.pathname.replace(/^\/api/, '')
  const body = typeof options.body === 'string' ? JSON.parse(options.body) : null
  window.welcomeTest.calls.push({ path, method: options.method || 'GET', body })
  const response = data => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
  if (path === '/auth/me') return response(user)
  if (path === '/auth/refresh') return response({ user, ...session, access_token: 'guide-test-token' })
  if (path.startsWith('/auth/')) return response(session)
  if (path === '/roles/access') return response({})
  if (path === '/profiles/preference-catalogs') return response({ genres: [{ id: 'fantasy', name: 'Fantasía' }], tropes: [] })
  if (path === '/profiles/me/onboarding/guide') {
    guide = { ...guide, ...body }; sessionStorage.setItem('guide-test-progress', JSON.stringify(guide))
    return response(guide)
  }
  if (path === '/profiles/me/onboarding') return response({ status: 'completed', guide,
    answers: { genre_ids: ['fantasy'], emotions: ['Intriga'], habit: 'Leo ocasionalmente', favorite_work_ids: [] },
    ai_status: 'completed', recommendation_source: 'gemini', recommendations: [{ work_id: registrationBooks[0].id, title: registrationBooks[0].volumeInfo.title, authors: registrationBooks[0].volumeInfo.authors, cover_url: registrationBooks[0].volumeInfo.imageLinks.thumbnail, explanation: 'Una historia que conecta con tus preferencias.' }] })
  if (path === '/profiles/me/onboarding/library') return response({ status: 'synced' })
  if (path === '/readings/me') return response(readings)
  if (path === '/readings/library' && options.method === 'POST') {
    const book = registrationBooks.find(item => item.id === body.book_ref) || registrationBooks[0]
    const reading = { reading_id: 'guide-reading', work_id: book.id, edition_id: null, edition_optional: true,
      book_ref: book.id, book_title: book.volumeInfo.title, status: 'pending', current_page: 0, total_pages: null, progress_percent: null, notebook: {}, catalog_volume: book }
    readings = [reading]; sessionStorage.setItem('guide-test-readings', JSON.stringify(readings))
    return response(reading)
  }
  if (path === '/books') return response({ items: registrationBooks, has_more: false })
  if (path.startsWith('/books/')) return response(registrationBooks.find(book => book.id === decodeURIComponent(path.slice(7))) || registrationBooks[0])
  if (path.startsWith('/reviews/by-book/')) return response({ items: [], has_more: false })
  if (path === '/reviews/me') return response(null)
  if (path.startsWith('/me/ai/')) return response({ scope: path.endsWith('/profile') ? 'profile' : 'book', analysis: null, job: null, evidence: [], library_summary: { total: readings.length, rated: 0, pending: readings.length } })
  if (path === '/analytics/me/free-usage') return response({})
  return response([])
}

export default function Profile() {
  const [params] = useSearchParams()
  return <><header><h1>Mi perfil</h1><nav><Link to="/profile?tab=analysis">Mis análisis</Link> · <Link to="/profile?tab=library">Mi biblioteca</Link></nav></header>
    {params.get('tab') === 'analysis' ? <InsightsPage><InitialLiteraryDNA /></InsightsPage> : <LibraryPage />}</>
}
createRoot(document.getElementById('root')).render(<BrowserRouter><ThemeProvider><AuthProvider><LibraryProvider><main id="main-content" style={{ maxWidth: 1100, margin: '24px auto', padding: 20 }}><WelcomeGuide /><Routes>
  <Route path="/profile" element={<Profile />} /><Route path="/books" element={<BooksPage />} /><Route path="/books/:id" element={<BookDetailPage />} /><Route path="/library/:id" element={<LibraryBookPage />} /><Route path="*" element={<Navigate to="/profile?tab=analysis" replace />} />
</Routes></main></LibraryProvider></AuthProvider></ThemeProvider></BrowserRouter>)
