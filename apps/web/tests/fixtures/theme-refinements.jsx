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
let preferences = { can_view: true, visible_sections: ['biography', 'genres', 'tropes', 'intensities'], profile_visibility: 'public', public_sections: ['biography', 'genres', 'tropes', 'intensities'], id: 'fixture', profile_id: 'fixture', display_name: 'Perfil de prueba', avatar_url: null, biography: 'Historia guardada', genres: genres.slice(0, 5), tropes: tropes.slice(0, 5), intensities: intensities.slice(0, 5).map(item => ({ ...item, level: 3 })), featured_category_id: 'terror' }
window.profileModalTest = { saves: [], attempts: [], failSave: false, failCatalog: false, delay: 50 }
const qa = window.profileModalTest
const fixtureParams = new URLSearchParams(location.search)
const fixtureRole = fixtureParams.get('role') || 'admin'
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
    ...(Object.hasOwn(fields, 'literary_crush') ? { literary_crush: fields.literary_crush } : {}),
    ...(Object.hasOwn(fields, 'essential_books') ? { essential_books: fields.essential_books } : {}),
    ...(Object.hasOwn(fields, 'story_illustration') ? { story_illustration: fields.story_illustration } : {}),
    ...(Object.hasOwn(fields, 'favorite_quotes') ? { favorite_quotes: fields.favorite_quotes } : {}),
    ...(Object.hasOwn(fields, 'biography') ? { biography: fields.biography } : {}),
    ...(fields.genre_ids ? { genres: fields.genre_ids.map(id => genres.find(item => item.id === id)) } : {}),
    ...(fields.trope_ids ? { tropes: tropes.filter(item => fields.trope_ids.includes(item.id)) } : {}),
    ...(fields.intensities ? { intensities: fields.intensities.map(item => ({ ...intensities.find(option => option.id === item.category_id), level: item.level })) } : {}),
    ...(Object.hasOwn(fields, 'featured_category_id') ? { featured_category_id: fields.featured_category_id } : {}),
  }
  return preferences
}
const realFetch = window.fetch
const volume={id:'book-fixture',volumeInfo:{title:'Historias entre estrellas',authors:['Autora de prueba'],language:'es',pageCount:180,imageLinks:{thumbnail:'/images/story-books-coffee.png'}},libria:{workId:'work-fixture',editionId:'edition-fixture',catalogOrigin:'libria',editionCount:1}}
const account={id:'fixture',username:'reader_fixture',display_name:'Perfil de prueba',role:fixtureRole,email:'fixture@example.com',email_verified:true,account_status:'active',suspended:false,google_linked:false,biography:'Una comunidad para leer',avatar_url:null}
const post={id:'post-fixture',user_id:'fixture',author_profile_id:'personal-fixture',author:'Perfil de prueba',author_role:fixtureRole,created_at:'2026-11-15T12:00:00Z',source:'community',kind:'community',publication_type:'news',feed_item_type:'publication',title:'Una nueva historia',body:'Compartimos libros e historias para descubrir nuevos mundos.',book_ref:'book-fixture',book_title:volume.volumeInfo.title,book_cover_url:'/images/story-books-coffee.png',images:[],like_count:2,comment_count:0,view_count:3,capabilities:{can_view:true,can_like:true,can_comment:true}}
const categories=['progress','started','finished','reviews','social','events','launches','announcements','promotions']
// Optional populated scene for visual review; never supplies production content.
const richMural = fixtureParams.get('scene') === 'mural'
const activityItems = kind => Array.from({length:4},(_,i)=>({...post,id:`${kind}-${i}`,feed_item_type:'reading_event',reading_event:kind,author:['Valentina Soto','Camila Torres','Javier Medina','Isabel Fuentes'][i],book_title:['Historias entre estrellas','Un camino de tinta','La biblioteca secreta','Al otro lado del libro'][i],book_author:'Autora de prueba',progress_percent:[87,47,59,32][i],book_cover_url:['/images/story-books-coffee.png','/images/story-books-cat.png','/images/story-books-candles.png','/images/story-books-cat-candle.png'][i]}))
window.fetch=(input,options={})=>{
 const url=new URL(input,location.href),path=url.pathname
 if(!path.includes('/api/'))return realFetch(input,options)
 let data=[]
 if(path.endsWith('/me/notification-inbox'))data={items:[],has_more:false}
 else if(path.endsWith('/roles/access'))data={admin:true,catalog_preview:true}
 else if(path.endsWith('/analytics/access'))data={group:true}
 else if(path.endsWith('/mural'))data={audience:'community',categories:Object.fromEntries(categories.map(k=>[k,{items:richMural&&['progress','started','finished'].includes(k)?activityItems(k==='started'?'start':k==='finished'?'finish':'progress'):k==='social'?[post]:[],has_more:false}]))}
 else if(path.includes('/mural/'))data={items:[],next_cursor:null}
 else if(path.endsWith('/accounts/me'))data=account
 else if(path.endsWith('/accounts/me/sessions'))data=[{id:'fixture-session',last_activity_at:'2026-11-15T12:00:00Z'}]
 else if(path.endsWith('/accounts/admin'))data={items:[account],total:1}
 else if(path.endsWith('/roles/requests/pending'))data=[]
 else if(path.endsWith('/roles/me/influencer-permissions'))data={suspended:false}
 else if(path.endsWith('/auth/google/link'))data={linked:false,email:'fixture@example.com',email_verified:false}
 else if(path.endsWith('/profiles/me'))data=[{id:'personal-fixture',kind:'personal',display_name:account.display_name,can_publish:true,role:fixtureRole}]
 else if(path.endsWith('/readings/me'))data=[{reading_id:'reading-fixture',book_ref:'book-fixture',book_title:volume.volumeInfo.title,work_id:'work-fixture',status:'reading',current_page:32,total_pages:180,progress_percent:18,catalog_volume:volume}]
 else if(path.endsWith('/books'))data={items:[volume],has_more:false}
 else if(path.includes('/books/'))data=volume
 else if(path.endsWith('/events'))data={items:[],has_more:false,next_cursor:null}
 else if(path.endsWith('/recommendations/state'))data={status:'locked',minimum_books:1,book_count:0,missing_books:1}
 else if(path.includes('/usage'))data={used:0,limit:10,remaining:10}
 else if(path.includes('/social/summary'))data={profile_id:'fixture',followers_count:0,following_count:0}
 else if(path.endsWith('/notifications/unread-count'))data={count:0}
 return Promise.resolve(new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}}))
}
history.replaceState(null, '', location.search.includes('public') ? '/profiles/fixture' : '/profile')
createRoot(document.getElementById('root')).render(<StrictMode><BrowserRouter><AuthProvider><ThemeProvider><LibraryProvider><App /></LibraryProvider></ThemeProvider></AuthProvider></BrowserRouter></StrictMode>)
