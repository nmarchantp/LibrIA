import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider, useAuth } from '/src/context/AuthContext'
import { LibraryProvider } from '/src/context/LibraryContext'
import { ThemeProvider } from '/src/context/ThemeContext'
import { authService } from '/src/services/authService'
import FeedCard from '/src/components/FeedCard'
import { toFeedPost } from '/src/services/feedService'
import '/src/styles.css'
import '/src/theme/themes.css'

const longTitle = 'La biblioteca de los secretos olvidados y las historias que cruzaron todos los mares hasta encontrar su último refugio entre las estrellas'
const cover = '/images/profile-reading-nook.png'
const posts = [
  { id: 'sixteen', book_title: 'El nombre del viento', progress_percent: 16, book_cover_url: cover },
  { id: 'complete', book_title: 'Una lectura terminada', progress_percent: 100, book_cover_url: cover },
  { id: 'long', book_title: longTitle, progress_percent: 16, book_cover_url: null },
  { id: 'broken', book_title: 'Portada no disponible', progress_percent: 100, book_cover_url: 'data:image/png;base64,broken' },
].map(post => ({ ...post, book_ref: post.id, kind: 'progress', feed_item_type: 'reading_event', source: 'reading', author: 'Ana Lectora', author_role: 'lector', created_at: '2026-11-07T12:00:00Z', body: `Llegó al ${post.progress_percent} % de "${post.book_title}".` }))
posts.push({ id: 'review', kind: 'reviews', title: 'Una reseña que permanece igual', body: 'Texto de la reseña.', author: 'Ana Lectora', author_role: 'lector', rating: 4, created_at: '2026-11-07T12:00:00Z' })
window.feedTestRequests = []
localStorage.setItem('libria_token', 'isolated-feed-test')
authService.me = async () => ({ id: 'fixture', display_name: 'Ana Lectora', role: 'lector', capabilities: [] })
const realFetch = window.fetch.bind(window)
window.fetch = (url, options) => {
  const path = String(url)
  if (!path.includes('/api/')) return realFetch(url, options)
  window.feedTestRequests.push({ url: path, method: options?.method || 'GET' })
  let data = []
  if (path.endsWith('/posts')) data = posts
  else if (path.includes('/comments')) data = [{ id: 'comment', author: 'Otra lectora', author_role: 'lector', body: '¡Buen avance!', created_at: '2026-11-07T12:00:00Z' }]
  else if (path.endsWith('/readings/me')) data = posts.filter(post => post.book_ref).map(post => ({ book_ref: post.book_ref, book_title: post.book_title, status: 'reading', progress_percent: post.progress_percent, catalog_volume: { id: post.book_ref, volumeInfo: { title: post.book_title, authors: ['Autora de prueba'] } } }))
  else if (path.includes('/analytics/access')) data = { group: false }
  return Promise.resolve(new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } }))
}
export default function Fixture() {
  const { user, loading } = useAuth()
  return user && !loading ? <main className="social-main"><div className="mural-layout"><section className="mural-feed"><div className="feed-posts">{posts.map(item => <FeedCard key={item.id} post={toFeedPost(item)} />)}</div></section></div></main> : null
}
createRoot(document.getElementById('root')).render(<BrowserRouter><AuthProvider><ThemeProvider><LibraryProvider><Fixture /></LibraryProvider></ThemeProvider></AuthProvider></BrowserRouter>)
