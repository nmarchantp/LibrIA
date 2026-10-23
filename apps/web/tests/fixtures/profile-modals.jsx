// Isolated browser fixture: never imported by the application entry point.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '/src/context/AuthContext'
import { LibraryProvider } from '/src/context/LibraryContext'
import { ThemeProvider } from '/src/context/ThemeContext'
import { authService } from '/src/services/authService'
import { profileService } from '/src/services/profileService'
import App from '/src/App'
import '/src/styles.css'
import '/src/theme/themes.css'

const genres = ['Romance', 'Fantasía', 'Misterio', 'Terror', 'Poesía', 'Aventura'].map((name, i) => ({ id: `genre-${i}`, name }))
const tropes = ['Magia', 'Dragones', 'Brujas', 'Vampiros', 'Familia encontrada', 'Amor prohibido'].map((name, i) => ({ id: `trope-${i}`, name, group: i < 4 ? 'Fantasía y magia' : 'Personajes y emociones' }))
const intensities = [['romance', 'Romance', 'heart'], ['spicy', 'Spicy', 'flame'], ['terror', 'Terror', 'ghost'], ['humor', 'Humor', 'smile'], ['accion', 'Acción', 'zap'], ['fantasia', 'Fantasía', 'sparkles']].map(([id, name, icon]) => ({ id, name, icon, color: 'mystic', levels: [1, 2, 3, 4, 5].map(n => `${name}: descripción de prueba ${n}`) }))
let preferences = { id: 'fixture', profile_id: 'fixture', display_name: 'Perfil de prueba', avatar_url: null, biography: 'Historia guardada', genres: genres.slice(0, 5), tropes: tropes.slice(0, 5), intensities: intensities.slice(0, 5).map(item => ({ ...item, level: 3 })), featured_category_id: 'terror' }
window.profileModalTest = { saves: [], attempts: [], failSave: false, failCatalog: false, delay: 50 }
const qa = window.profileModalTest
const fixtureParams = new URLSearchParams(location.search)
const fixtureRole = fixtureParams.get('role') || 'lector'
localStorage.setItem('libria_token', 'isolated-ui-test')
authService.me = async () => ({ id: 'fixture', display_name: 'Perfil de prueba', role: fixtureRole, email: 'fixture@example.com', created_at: '2026-01-02', capabilities: [] })
profileService.mine = async () => preferences
profileService.community = async () => preferences
profileService.catalogs = async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  if (qa.failCatalog) throw new Error('Catálogo no disponible')
  return { genres, tropes, intensities }
}
profileService.readingGenres = async () => ({ status: 'no_finished_books' })
profileService.save = async fields => {
  qa.attempts.push(structuredClone(fields))
  await new Promise(resolve => setTimeout(resolve, qa.delay))
  if (qa.failSave) throw new Error('Error de guardado de prueba')
  qa.saves.push(structuredClone(fields))
  preferences = {
    ...preferences,
    ...(Object.hasOwn(fields, 'biography') ? { biography: fields.biography } : {}),
    ...(fields.genre_ids ? { genres: fields.genre_ids.map(id => genres.find(item => item.id === id)) } : {}),
    ...(fields.trope_ids ? { tropes: tropes.filter(item => fields.trope_ids.includes(item.id)) } : {}),
    ...(fields.intensities ? { intensities: fields.intensities.map(item => ({ ...intensities.find(option => option.id === item.category_id), level: item.level })) } : {}),
    ...(Object.hasOwn(fields, 'featured_category_id') ? { featured_category_id: fields.featured_category_id } : {}),
  }
  return preferences
}
const realFetch = window.fetch
window.fetch = (url, options) => String(url).includes('/api/') ? Promise.resolve(new Response(String(url).includes('/analytics/access') ? JSON.stringify({ group: fixtureParams.has('group') }) : '[]', { status: 200, headers: { 'Content-Type': 'application/json' } })) : realFetch(url, options)
history.replaceState(null, '', location.search.includes('public') ? '/profiles/fixture' : '/profile')
createRoot(document.getElementById('root')).render(<StrictMode><BrowserRouter><AuthProvider><ThemeProvider><LibraryProvider><App /></LibraryProvider></ThemeProvider></AuthProvider></BrowserRouter></StrictMode>)
