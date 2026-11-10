import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider, useTheme } from '/src/context/ThemeContext'
import ProfileHeader from '/src/components/ProfileHeader'
import ProfileSocialHub from '/src/components/ProfileSocialHub'
import '/src/styles.css'
import '/src/theme/themes.css'
import '/src/pages/ProfilePage.css'

localStorage.setItem('libria_token', 'isolated-test')
function ThemeControls() {
  const { selectTheme } = useTheme()
  useEffect(() => { window.socialTest.selectTheme = selectTheme }, [selectTheme])
  return null
}
window.decodeSharedQr = async (source, width) => {
  const { default: jsQR } = await import('jsqr')
  const image = source ? new Image() : document.querySelector('.profile-share-qr img')
  if (source) { image.src = source; await image.decode() }
  const canvas = document.createElement('canvas')
  canvas.width = width || image.naturalWidth; canvas.height = width || image.naturalHeight
  const context = canvas.getContext('2d')
  context.drawImage(image, 0, 0, canvas.width, canvas.height)
  return jsQR(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height)?.data || null
}
window.checkProfileQr = async (url, theme, width) => {
  const { createProfileQr } = await import('/src/services/profileQr')
  return window.decodeSharedQr(await createProfileQr(url, theme), width)
}
const people = [{ id: 'person-1', display_name: 'Camila Lectora', avatar_url: null }, { id: 'person-2', display_name: 'Diego Escritor', avatar_url: null }]
window.socialTest = { following: 3, saves: [], follows: [] }
const actualFetch = window.fetch
window.fetch = async (url, options = {}) => {
  const path = String(url)
  if (!path.includes('/api/')) return actualFetch(url, options)
  const payload = path.includes('/social-summary') ? { profile_id: 'profile-me', finished_books: 7, followers: 2, following: window.socialTest.following }
    : path.includes('/connections?') ? { items: people, has_more: false }
    : path.includes('/discover/people') ? { items: people.filter(person => person.display_name.toLowerCase().includes(new URL(path).searchParams.get('q')?.toLowerCase() || '')), has_more: false }
    : { following: options.method !== 'DELETE' }
  if (path.endsWith('/follow')) { window.socialTest.follows.push({ path, method: options.method }); window.socialTest.following += options.method === 'DELETE' ? -1 : 1 }
  return new Response(options.method === 'DELETE' ? null : JSON.stringify(payload), { status: options.method === 'DELETE' ? 204 : 200, headers: { 'Content-Type': 'application/json' } })
}
function Fixture() {
  const [data, setData] = useState({ profile_id: 'profile-me', profile_visibility: 'public', public_sections: ['biography', 'genres'] })
  const preferences = { data, save: async fields => { window.socialTest.saves.push(fields); setData(previous => ({ ...previous, ...fields })) } }
  return <MemoryRouter><ThemeProvider><ThemeControls /><div className="social-main"><main className="profile-page page-width reader-profile reader-community-profile"><div className="reader-profile-main"><ProfileHeader user={{ display_name: 'Valentina Lectora', created_at: '2026-01-02', avatar_url: null }} /><ProfileSocialHub preferences={preferences} displayName="Valentina Lectora" /><nav className="profile-tabs reader-profile-tabs"><button>Sobre mí</button><button>Mi biblioteca</button><button>Mi actividad</button></nav></div></main></div></ThemeProvider></MemoryRouter>
}
createRoot(document.getElementById('root')).render(<Fixture />)
