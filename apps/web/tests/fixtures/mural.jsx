// Isolated demo data for browser tests only. Never imported by production.
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '/src/context/AuthContext'
import { LibraryProvider } from '/src/context/LibraryContext'
import { ThemeProvider } from '/src/context/ThemeContext'
import { authService } from '/src/services/authService'
import HomePage from '/src/pages/HomePage'
import EventsPage from '/src/pages/EventsPage'
import Layout from '/src/components/Layout'
import '/src/styles.css'
import '/src/theme/themes.css'

const count = Number(new URLSearchParams(location.search).get('count') ?? 12)
const emptyComments = new URLSearchParams(location.search).get('comments') === 'empty'
const role = new URLSearchParams(location.search).get('role') || 'lector'
const persistEvents=new URLSearchParams(location.search).has('persist_events')
const eventStateKey='libria-event-test-state'
const eventState=persistEvents?JSON.parse(localStorage.getItem(eventStateKey)||'{}'):{}
const categoryNames = ['progress', 'started', 'finished', 'reviews', 'social']
const items = Object.fromEntries(categoryNames.map(category => [category, Array.from({ length: count }, (_, i) => ({
  id: `${category}-${i}`, user_id: `user-${i}`, author_profile_id: `profile-${i}`, author: `Lector ${i + 1}`,
  author_role: 'lector', created_at: '2026-11-08T12:00:00Z',
  kind: category === 'reviews' ? 'reviews' : category === 'social' ? 'community' : 'progress',
  feed_item_type: category === 'reviews' ? 'review' : category === 'social' ? 'publication' : 'reading_event',
  reading_event: { progress: 'progress', started: 'start', finished: 'finish' }[category] || null,
  book_ref: category === 'social' ? null : `book-${i}`, book_title: category === 'social' ? null : i === 1 ? 'La biblioteca de las historias que viajaron hasta el otro lado del mundo' : `Una historia para descubrir ${i + 1}`,
  title: category === 'social' ? 'Una conversación sobre todas las historias que nos acompañan' : null,
  book_author: 'Autora de prueba', book_cover_url: category === 'social' || i % 3 === 1 ? null : '/images/profile-reading-nook.png',
  progress_percent: category === 'progress' ? i === 2 ? null : 16 + i : category === 'finished' ? 100 : null,
  page: 82, rating: category === 'reviews' ? 4.5 : null, images: [],
  is_spoiler: category === 'reviews' && i === 1, body: category === 'reviews' && i === 1 ? 'PRIVATE SPOILER TEXT' : category === 'social' ? 'Una nota para compartir nuestra pasión por los libros.' : 'Una lectura que deja huella.',
  following_author: false, like_count: 2, liked_by_me: false, comment_count: 1, view_count: 0,
  can_manage: category==='reviews'&&i===0,
  capabilities: { can_like: true, can_comment: true, can_view: true, can_register_view: true },
  observed_at: '2020-01-01T00:00:00.000Z',
}))]))
for (const [category, publication_type] of [['events', 'event'], ['launches', 'launch'], ['announcements', 'news'], ['promotions', 'promotion']]) {
  items[category] = items.social.map((item, index) => ({ ...item, id: `${category}-${index}`, author_role: 'admin', publication_type,
    source: category === 'events' ? 'event' : 'community', title: `Publicación completa de ${category} ${index + 1}`,
    body: 'Texto completo de la publicación, con todos los detalles del encuentro y su historia. '.repeat(8),
    images: index === 5 ? [] : ['story-books-candles-plain.png','story-books-coffee.png','story-books-cat.png','story-books-cat-candle.png','reading-year-books.png','profile-reading-nook.png'].slice(0,[1,2,4,6][index%4]).map(name=>new URL(`/images/${name}`,location.origin).href),
    can_edit_book_cover: index===0,
    can_manage: index===0,
    book_ref: index === 5 ? null : 'book-0', book_title: index === 5 ? null : 'Libro enlazado de la publicación', book_cover_url: index === 5 ? null : '/images/profile-reading-nook.png',
  }))
  if(category==='events')items[category]=items[category].map((item,index)=>({...item,event_details:{id:item.id,start_date:'2026-11-12',start_time:'18:00',end_date:null,end_time:null,timezone:'America/Santiago',location:'Santiago de Chile',organizer:'Comunidad LibrIA',category:'fair',starts_at:'2026-11-12T21:00:00Z',ends_at:null,attending:false,attendee_count:0,schedule_revision:1,schedule_update:null,observed_at:'2020-01-01T00:00:00.000Z'},...eventState[item.id]})).filter(item=>!item.deleted)
}
window.muralTest = { requests: [], fail: false, noContacts: false, failMore: false }
if(persistEvents){const stella=items.events.find(item=>item.id==='events-0');if(stella){if(!eventState[stella.id])stella.title='Stella a Chile';stella.images=['story-books-candles-plain.png','story-books-coffee.png','story-books-cat.png','story-books-cat-candle.png','reading-year-books.png','profile-reading-nook.png'].map(name=>new URL(`/images/${name}`,location.origin).href)}}
localStorage.setItem('libria_token', 'isolated-mural-test')
authService.me = async () => ({ id: 'fixture', display_name: 'Lector de prueba', role, capabilities: [] })
const realFetch = window.fetch.bind(window)
const counters = new Map(), comments = new Map(), customCovers = new Map()
const keyFor = item => `${item.feed_item_type}:${item.id}`
const countsFor = item => {
  const key = keyFor(item)
  if (!counters.has(key)) counters.set(key, { like_count: 2, liked_by_me: false, comment_count: emptyComments ? 0 : 1, view_count: 0,
    capabilities: item.capabilities, observed_at: item.observed_at })
  return counters.get(key)
}
const decorate = item => ({ ...item, ...countsFor(item), custom_book_cover_url: customCovers.get(item.id) || null })
const saveEvent=item=>{if(persistEvents){eventState[item.id]={title:item.title,body:item.body,event_details:item.event_details,deleted:item.deleted||false};localStorage.setItem(eventStateKey,JSON.stringify(eventState))}}
window.fetch = (url, options) => {
  const path = String(url)
  if (!path.includes('/api/')) return realFetch(url, options)
  const parsed = new URL(path)
  window.muralTest.requests.push({ path: parsed.pathname + parsed.search, method: options?.method || 'GET' })
  let data = [], status = 200
  if (parsed.pathname.endsWith('/profiles/me')) data = [{ id: 'personal-fixture', kind: 'personal' }]
  else if (parsed.pathname.endsWith('/readings/me')) data = [{ book_ref: 'reading-fixture', book_title: 'Lectura en curso', status: 'reading', progress_percent: 16, current_page: 16, total_pages: 100 }]
  else if (/\/posts\/[^/]+$/.test(parsed.pathname)||/\/reviews\/[^/]+$/.test(parsed.pathname)) {
    const id=parsed.pathname.split('/').at(-1),item=Object.values(items).flat().find(candidate=>candidate.id===id),method=options?.method||'GET'
    if(!item)return Promise.resolve(new Response('{}',{status:404}))
    if(window.muralTest.failSave&&method==='PUT')return Promise.resolve(new Response(JSON.stringify({detail:'Error al guardar de prueba'}),{status:422,headers:{'Content-Type':'application/json'}}))
    if(method==='DELETE'){item.deleted=true;saveEvent(item);for(const category of Object.keys(items))items[category]=items[category].filter(candidate=>candidate.id!==id);data={}}
    else if(method==='PUT'){
      if(options.body instanceof FormData){for(const key of ['body','title','publication_type','source','book_ref','book_title'])item[key]=options.body.get(key);if(options.body.has('book_cover'))customCovers.set(id,`/fixture-covers/${id}`);else if(options.body.get('cover_mode')==='catalog')customCovers.delete(id)
        if(options.body.has('event_details')){const next=JSON.parse(options.body.get('event_details')),old=item.event_details;const changed=old&&(old.start_date!==next.start_date||old.start_time!==next.start_time||old.end_date!==next.end_date||old.end_time!==next.end_time||old.timezone!==next.timezone);item.event_details={...old,...next,id:item.id,starts_at:new Date(`${next.start_date}T${next.start_time}:00-03:00`).toISOString(),schedule_revision:(old?.schedule_revision||1)+(changed?1:0),schedule_update:changed?{changed_at:new Date().toISOString(),previous_start:old.starts_at,previous_timezone:old.timezone}:old?.schedule_update||null,attending:old?.attending||false,attendee_count:old?.attendee_count||0,observed_at:new Date().toISOString()}}
      }
      else Object.assign(item,JSON.parse(options.body))
      saveEvent(item);data=decorate(item)
    }else data=decorate(item)
  }
  else if (parsed.pathname.endsWith('/book-cover')) {
    const id=parsed.pathname.split('/')[3]
    if(options?.method==='DELETE')customCovers.delete(id)
    else customCovers.set(id,`/fixture-covers/${id}`)
    data={custom_book_cover_url:customCovers.get(id)||null}
  }
  else if (parsed.pathname.includes('/activities/')) {
    const [, , , kind, id, action, commentId] = parsed.pathname.split('/')
    const item = Object.values(items).flat().find(candidate => candidate.feed_item_type === kind && candidate.id === id)
    if (!item) return Promise.resolve(new Response('{}', { status: 404 }))
    const key = keyFor(item), counter = countsFor(item), method = options?.method || 'GET'
    if (action === 'view' && method === 'PUT') counter.view_count = 1
    if (action === 'like') {
      if (window.muralTest.failLike) return Promise.resolve(new Response(JSON.stringify({ detail: 'No se pudo actualizar Me gusta.' }), { status: 503, headers: { 'Content-Type': 'application/json' } }))
      const enabled = method === 'PUT'
      if (counter.liked_by_me !== enabled) counter.like_count += enabled ? 1 : -1
      counter.liked_by_me = enabled
      if (enabled) counter.view_count = 1
    }
    if (action === 'comments') {
      if (!comments.has(key)) comments.set(key, emptyComments ? [] : [{ id: 'original', author: 'Otra lectora', author_role: 'lector', body: 'Comentario conservado', created_at: '2026-11-08T12:00:00Z' }])
      if(commentId) {
        if(method==='DELETE'){comments.set(key,comments.get(key).filter(comment=>comment.id!==commentId));counter.comment_count--;data={interactions:{...counter,observed_at:new Date().toISOString()}}}
        else{const comment=comments.get(key).find(comment=>comment.id===commentId);comment.body=JSON.parse(options.body).body;comment.edited_at=new Date().toISOString();data={comment,interactions:{...counter,observed_at:new Date().toISOString()}}}
      }else if (method === 'POST') {
        const comment = { id: `new-${comments.get(key).length}`, user_id:'fixture', author: 'Lector de prueba', author_role: 'lector', body: JSON.parse(options.body).body, created_at: '2026-11-08T12:00:00Z' }
        comments.get(key).push(comment); counter.comment_count++; counter.view_count = 1
        counter.observed_at = new Date().toISOString()
        data = { comment, interactions: { ...counter } }
      } else data = comments.get(key)
    } else { counter.observed_at = new Date().toISOString(); data = { ...counter } }
  } else if (/\/events\/[^/]+\/attendance$/.test(parsed.pathname)) {
    const id=parsed.pathname.split('/')[3],item=items.events.find(item=>item.id===id)
    if(!item)return Promise.resolve(new Response('{}',{status:404}))
    const current=item.event_details,method=options?.method||'GET'
    if(method!=='GET'){const enabled=method==='PUT';if(current.attending!==enabled)current.attendee_count+=enabled?1:-1;current.attending=enabled;saveEvent(item)}
    current.observed_at=new Date().toISOString();data={...current}
  } else if (parsed.pathname==='/api/events') {
    data={items:items.events.filter(item=>item.event_details).sort((a,b)=>a.event_details.starts_at.localeCompare(b.event_details.starts_at)).map(decorate),has_more:false}
  } else if (parsed.pathname.endsWith('/mural')) {
    if (window.muralTest.fail) status = 500
    data = { audience: parsed.searchParams.get('audience'), categories: Object.fromEntries(categoryNames.map(category => [category, { items: window.muralTest.noContacts && parsed.searchParams.get('audience') === 'contacts' ? [] : items[category].slice(0, 9).map(decorate), has_more: count > 9 }])) }
  } else if (parsed.pathname.includes('/mural/')) {
    const category = parsed.pathname.split('/').at(-1), more = parsed.searchParams.has('cursor')
    if (more && window.muralTest.failMore) status = 500
    data = { items: window.muralTest.noContacts && parsed.searchParams.get('audience') === 'contacts' ? [] : items[category].slice(more ? 7 : 0, more ? undefined : 8).map(decorate), next_cursor: !more && count > 8 ? 'fixture-cursor' : null }
  } else if (parsed.pathname.endsWith('/comments')) {
    data = options?.method === 'POST' ? { id: 'new', author: 'Lector de prueba', author_role: 'lector', body: JSON.parse(options.body).body, created_at: '2026-11-08T12:00:00Z' } : [{ id: 'original', author: 'Otra lectora', author_role: 'lector', body: 'Comentario conservado', created_at: '2026-11-08T12:00:00Z' }]
  } else if (parsed.pathname.endsWith('/like')) data = { like_count: 3, liked_by_me: true }
  else if (parsed.pathname.endsWith('/follow')) data = { following: true }
  else if (path.includes('/analytics/access')) data = { group: false }
  return Promise.resolve(new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }))
}
export default function Fixture() {
  const { user, loading } = useAuth()
  return user && !loading ? <Routes><Route element={<Layout />}><Route path="/events" element={<EventsPage />} /><Route path="*" element={<HomePage />} /></Route></Routes> : null
}
createRoot(document.getElementById('root')).render(<BrowserRouter><AuthProvider><ThemeProvider><LibraryProvider><Fixture /></LibraryProvider></ThemeProvider></AuthProvider></BrowserRouter>)
