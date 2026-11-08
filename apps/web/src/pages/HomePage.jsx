import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowUpRight, BookOpen, ChartNoAxesColumnIncreasing, Check, MessageCircle, RefreshCw, Star } from 'lucide-react'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useLibrary } from '../context/LibraryContext'
import BookCover from '../components/BookCover'
import PostComposer from '../components/PostComposer'
import MuralCarousel from '../components/MuralCarousel'
import MuralActivityCard from '../components/MuralActivityCard'
import MuralActivityDialog from '../components/MuralActivityDialog'
import MuralPublication from '../components/MuralPublication'
import ContentManagementDialog from '../components/ContentManagementDialog'
import { MuralManagementContext } from '../context/MuralManagementContext'
import useMural from '../hooks/useMural'
import { ActivityInteractionProvider, useActivityStore } from '../context/ActivityInteractionContext'
import './HomePage.css'
import './MuralPage.css'

const categories = [
  { id: 'progress', title: 'Avances de lecturas', description: 'El progreso más reciente de cada lectura compartida.', icon: ChartNoAxesColumnIncreasing },
  { id: 'started', title: 'Empezaron a leer', description: 'Nuevas historias que acaban de comenzar.', icon: BookOpen },
  { id: 'finished', title: 'Terminados por tus contactos', description: 'Lecturas que acaban de completar.', icon: Check },
  { id: 'reviews', title: 'Reseñas recientes', description: 'Opiniones y valoraciones para descubrir tu próxima lectura.', icon: Star },
  { id: 'social', title: 'Publicaciones de la comunidad', description: 'Notas, teorías, anuncios y conversaciones literarias.', icon: MessageCircle },
]
const publicationCategories = [
  { id: 'events', title: 'Eventos', description: 'Encuentros y actividades de nuestra comunidad literaria.' },
  { id: 'launches', title: 'Lanzamientos', description: 'Nuevos libros e historias que llegan a la comunidad.' },
  { id: 'announcements', title: 'Anuncios', description: 'Novedades y anuncios de la comunidad.' },
  { id: 'promotions', title: 'Promociones', description: 'Promociones compartidas por la comunidad.' },
]

function MuralContent() {
  const { user } = useAuth()
  const { books } = useLibrary()
  const interactions = useActivityStore()
  const [params, setParams] = useSearchParams()
  const audience = params.get('audience') === 'contacts' ? 'contacts' : 'community'
  const category = [...categories, ...publicationCategories].find(item => item.id === params.get('category')) || null
  const widePublications = category?.id === 'social' || publicationCategories.some(item => item.id === category?.id)
  const activeTab = publicationCategories.some(item => item.id === category?.id) ? category.id : audience
  const navigation = useRef(null)
  const [refresh, setRefresh] = useState(0)
  const [selected, setSelected] = useState(null)
  const [management,setManagement] = useState(null)
  const [savedMessage,setSavedMessage]=useState('')
  const [profiles, setProfiles] = useState([])
  const [profileError, setProfileError] = useState('')
  const savedScroll = useRef(0)
  const feed = useMural(user.id, audience, category?.id, refresh)
  useEffect(() => {
    let active = true
    const controller = new AbortController()
    apiRequest('/profiles/me', { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, signal: controller.signal })
      .then(data => { if (active) { setProfiles(data); setProfileError('') } })
      .catch(() => { if (active) setProfileError('No se pudieron cargar tus permisos de publicación.') })
    return () => { active = false; controller.abort() }
  }, [user.id, refresh])
  const selectedProfile = user.role !== 'lector' ? profiles.find(profile => profile.kind === 'personal') : null
  function chooseAudience(value) {
    setSavedMessage('')
    setSelected(null)
    savedScroll.current = 0
    setParams(current => { const next = new URLSearchParams(current); next.set('audience', value); next.delete('category'); return next })
  }
  function viewAll(value) {
    setSavedMessage('')
    savedScroll.current = window.scrollY
    setParams(current => { const next = new URLSearchParams(current); next.set('category', value); return next })
    window.scrollTo({ top: 0 })
  }
  useEffect(() => {
    const nav = navigation.current
    const revealSelected = () => {
      const button = nav?.querySelector('[aria-pressed="true"]')
      if (!button) return
      const container = nav.getBoundingClientRect(), selected = button.getBoundingClientRect()
      if (selected.left < container.left || selected.right > container.right) {
        nav.scrollTo({ left: nav.scrollLeft + selected.left - container.left - (container.width - selected.width) / 2 })
      }
    }
    revealSelected()
    const observer = new ResizeObserver(revealSelected)
    if (nav) observer.observe(nav)
    return () => observer.disconnect()
  }, [activeTab])
  useEffect(() => {
    if (!category && !feed.loading) {
      const frame = requestAnimationFrame(() => window.scrollTo({ top: savedScroll.current }))
      return () => cancelAnimationFrame(frame)
    }
  }, [category, feed.loading])
  const titleFor = item => item.id === 'finished' && audience === 'community' ? 'Terminados por la comunidad' : item.title
  const empty = audience === 'contacts' ? 'Todavía no hay actividades de tus contactos en esta categoría. Sigue perfiles para descubrir sus lecturas.' : 'Todavía no hay actividades públicas en esta categoría.'
  async function openActivity(item, comments = false) {
    if (await interactions.view(item, comments ? 'open_comments' : 'open')) setSelected({ item, comments })
  }
  const renderItem = item => <MuralActivityCard item={item} onOpen={openActivity} />

  return <MuralManagementContext.Provider value={{edit:item=>setManagement({action:'edit',item}),remove:item=>setManagement({action:'delete',item})}}><div className="mural-layout mural-screen">
    <section className="mural-feed" aria-labelledby="mural-title">
    <header className="mural-heading"><span className="kicker">TU COMUNIDAD LECTORA</span><h1 id="mural-title">Entre libros y personas.</h1><p>Descubre lo que otros leen, sienten y comparten.</p></header>
    {profileError && <p role="alert">{profileError}</p>}
    {savedMessage&&<p role="status">{savedMessage}</p>}
    {selectedProfile && !category && <PostComposer key={selectedProfile.id} role={user.role} profileId={selectedProfile.id} onCreated={() => setRefresh(value => value + 1)} />}
    <div className="mural-navigation">
      <nav ref={navigation} className="mural-audiences" aria-label="Secciones del mural">{[{ id: 'contacts', title: 'Contactos' }, { id: 'community', title: 'Comunidad' }, ...publicationCategories].map(item => <button key={item.id} aria-pressed={activeTab === item.id} onClick={() => item.id === 'contacts' || item.id === 'community' ? chooseAudience(item.id) : viewAll(item.id)}>{item.title}</button>)}</nav>
      <button className="mural-refresh" aria-label="Actualizar mural" disabled={feed.loading || feed.busy} onClick={() => setRefresh(value => value + 1)}><RefreshCw size={18} /></button>
    </div>
    {category && <div className="mural-history-heading"><h2>{titleFor(category)}</h2><p>{category.id === 'progress' ? 'Todos los avances compartidos, del más reciente al más antiguo.' : category.description}</p></div>}
    {feed.loading && <p className="mural-status" role="status">Cargando actividades…</p>}
    {feed.error && <div className="mural-status" role="alert"><p>{feed.error}</p><button onClick={() => setRefresh(value => value + 1)}>Reintentar</button></div>}
    {!feed.loading && !feed.error && feed.data && (category ? <>
      <div className={widePublications ? 'feed-posts mural-publications' : 'mural-history-grid'}>{feed.data.items.map(item => <div key={`${item.feed_item_type}:${item.id}`}>{widePublications ? <MuralPublication item={item} /> : renderItem(item)}</div>)}</div>
      {!feed.data.items.length && <p className="mural-status">{empty}</p>}
      {feed.moreError && <p role="alert">{feed.moreError}</p>}
      {feed.data.next_cursor && <button className="mural-load-more" disabled={feed.busy} onClick={feed.loadMore}>{feed.busy ? 'Cargando…' : feed.moreError ? 'Reintentar cargar más' : 'Cargar más'}</button>}
    </> : <div className="mural-categories">{categories.map(item => <MuralCarousel key={`${audience}:${item.id}`} title={titleFor(item)} description={item.description} icon={item.icon} items={feed.data.categories[item.id]?.items || []} empty={empty} onViewAll={() => viewAll(item.id)} renderItem={renderItem} />)}</div>)}
    </section>
    <aside className="mural-aside"><section className="reader-summary"><span className="kicker">TU RINCÓN</span><h2>Hola, {user.display_name.split(' ')[0]}</h2><p>Tu próxima página también tiene una historia.</p><Link to="/profile">Visitar mi perfil <ArrowUpRight size={16} /></Link></section>
      <section className="aside-reading"><h2><BookOpen size={18} /> Sigue leyendo</h2>{books.filter(book => book.status === 'Leyendo').map(book => <Link to={'/books/' + book.id} className="aside-book" key={book.id}><BookCover book={book} /><div><strong>{book.title}</strong><small>{book.progress}% leído · ejemplo</small></div></Link>)}<Link className="aside-link" to="/profile?tab=library">Ver mi biblioteca →</Link></section>
      <div className="community-note"><MessageCircle size={22} /><p>Un lugar para conversar sobre las historias que nos acompañan.</p><small>LibrIA · Comunidad lectora</small></div>
    </aside>
    {selected && <MuralActivityDialog key={`${selected.item.feed_item_type}:${selected.item.id}:${selected.comments}`} item={selected.item} openComments={selected.comments} onClose={() => setSelected(null)} />}
    {management&&<ContentManagementDialog target={management} onClose={()=>setManagement(null)} onSaved={result=>{setManagement(null);setSelected(null);setSavedMessage(result?.deleted?'Publicación eliminada.':'Cambios guardados.');setRefresh(value=>value+1)}} />}
  </div>
  </MuralManagementContext.Provider>
}

export default function HomePage() {
  const { user } = useAuth()
  return <ActivityInteractionProvider key={user.id}><MuralContent /></ActivityInteractionProvider>
}
