import { createRoot } from 'react-dom/client'
import { AuthProvider, useAuth } from '/src/context/AuthContext'
import { ThemeProvider } from '/src/context/ThemeContext'
import { authService } from '/src/services/authService'
import UserStories from '/src/components/UserStories'
import ProfileHeader from '/src/components/ProfileHeader'
import '/src/styles.css'
import '/src/theme/themes.css'
import '/src/pages/ProfilePage.css'

const user = { id: 'viewer', display_name: 'Valentina Lectora', role: 'lector', avatar_url: new URL('/images/story-books-cat.png', location.origin).href }
localStorage.setItem('libria_token', 'isolated-stories')
authService.me = async () => user
const expires_at = new Date(Date.now() + 86400000).toISOString()
const groups = [
  { profile_id: 'profile-me', display_name: user.display_name, is_owner: true, avatar_url: user.avatar_url, stories: [{ id: 's1', expires_at }, { id: 's2', expires_at }] },
  { profile_id: 'profile-other', display_name: 'Camila entre libros', is_owner: false, avatar_url: null, stories: [{ id: 's3', expires_at }] },
]
const canvas = document.createElement('canvas'); canvas.width = 108; canvas.height = 192
const ctx = canvas.getContext('2d'); ctx.fillStyle = '#725689'; ctx.fillRect(0, 0, 108, 192)
ctx.fillStyle = '#fff'; ctx.font = '12px sans-serif'; ctx.fillText('Entre páginas', 10, 95)
const image = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
const actualFetch = window.fetch
window.storyTest = { posts: 0, fail: false }
window.fetch = async (url, options = {}) => {
  const path = new URL(url, location.href).pathname
  if (!path.startsWith('/api/')) return actualFetch(url, options)
  let payload = {}
  if (path === '/api/stories') {
    if (options.method === 'POST') {
      window.storyTest.posts++
      groups[0].stories.push({ id: `new-${window.storyTest.posts}`, expires_at })
      payload = groups[0].stories.at(-1)
    } else if (window.storyTest.fail) return new Response(JSON.stringify({ detail: 'Error de carga de prueba' }), { status: 503 })
    else payload = { items: groups }
  } else if (path.endsWith('/image')) return new Response(image, { headers: { 'Content-Type': 'image/png' } })
  else if (options.method === 'PUT' && path.endsWith('/view')) {
    const id = path.split('/').at(-2)
    groups.forEach(group => { group.stories.forEach(story => { if (story.id === id) story.seen = true }) })
    return new Response(null, { status: 204 })
  } else if (options.method === 'DELETE') {
    groups.forEach(group => { group.stories = group.stories.filter(story => !path.endsWith('/' + story.id)) })
    return new Response(null, { status: 204 })
  }
  return new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } })
}
function Fixture() {
  const { loading } = useAuth()
  if (loading) return <p>Cargando sesión…</p>
  return <main style={{ maxWidth: 900, margin: '30px auto', padding: 20 }}><ProfileHeader user={user} /><UserStories /></main>
}
createRoot(document.getElementById('root')).render(<AuthProvider><ThemeProvider><Fixture /></ThemeProvider></AuthProvider>)
