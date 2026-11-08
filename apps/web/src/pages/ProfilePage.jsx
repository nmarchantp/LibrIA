import { BookOpen, BrainCircuit, CalendarDays, Library, Lightbulb, StickyNote, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import LibraryPage from './LibraryPage'
import InsightsPage from './InsightsPage'
import ProfileHeader from '../components/ProfileHeader'
import ProfilePanels from '../components/ProfilePanels'
import ProfileEvents from '../components/ProfileEvents'
import ProfilePersonalColumn from '../components/ProfilePersonalColumn'
import ProfileAboutSection from '../components/ProfileAboutSection'
import useLiteraryPreferences from '../hooks/useLiteraryPreferences'
import './ProfilePage.css'

function ProfileActivity({ userId }) {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    apiRequest('/posts?limit=100', { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      .then(items => { if (active) setPosts(items.filter(item => item.user_id === userId && ['note', 'theory'].includes(item.publication_type))) })
      .catch(() => { if (active) setError('No se pudo cargar tu muro.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [userId])
  if (loading) return <section className="profile-wall"><p role="status">Cargando tu muro…</p></section>
  if (error) return <section className="profile-wall"><p role="alert">{error}</p></section>
  if (!posts.length) return <section className="profile-empty"><BookOpen size={36} /><h2>Comparte tu historia lectora</h2><p>Tus notas y teorías sobre los libros aparecerán aquí y en el mural de la comunidad.</p><Link className="button primary" to="/profile?tab=library">Ir a mi biblioteca</Link></section>
  return <section className="profile-wall"><div className="profile-wall-heading"><span className="kicker">MI MURO</span><h2>Notas y teorías</h2></div><div className="profile-wall-grid">
    {posts.map(post => { const Icon = post.publication_type === 'note' ? StickyNote : Lightbulb; return <article className={`profile-wall-post ${post.publication_type}`} key={post.id}><Icon aria-hidden="true" /><span>{post.publication_type === 'note' ? 'NOTA' : 'TEORÍA'}</span><h3>{post.title}</h3><p>{post.body}</p>{post.book_ref && <Link to={`/books/${post.book_ref}`}>Ver libro →</Link>}</article> })}
  </div></section>
}

export default function ProfilePage() {
  const { user } = useAuth()
  const preferences = useLiteraryPreferences()
  const [editMode, setEditMode] = useState(false)
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = ['about', 'activity', 'library', 'analysis', 'events'].includes(requested) ? requested : 'about'
  if (requested === 'account' || requested === 'personalization') {
    return <Navigate to={requested === 'personalization' ? '/settings?tab=personalization' : '/settings'} replace />
  }
  const renderPanel = (value, active) => {
  switch (value) {
    case 'events':
      return <ProfileEvents active={active} />
    case 'library':
      return <LibraryPage />
    case 'analysis':
      return <InsightsPage active={active} />
    case 'activity':
      return <ProfileActivity userId={user.id} />
    default:
      return <ProfileAboutSection key={user.id} editMode={editMode} onToggleEdit={() => setEditMode(value => !value)} biography={user.biography} preferences={preferences.data} loading={preferences.loading} error={preferences.error} onRetry={preferences.retry} onSave={preferences.save} />
  }
  }

  return <div className="profile-page page-width reader-profile">
    <div className="reader-profile-main">
      <ProfileHeader key={user.id} user={user} />
      <nav className="profile-tabs reader-profile-tabs" aria-label="Secciones de mi perfil">{[['about', 'Sobre mí', BookOpen], ['library', 'Mi biblioteca', Library], ['analysis', 'Mis análisis', BrainCircuit], ['activity', 'Mi actividad', UserRound], ['events', 'Mis eventos', CalendarDays]].map(([value, label, Icon]) => <button key={value} className={tab === value ? 'active' : ''} aria-pressed={tab === value} onClick={() => setParams(current => { const next = new URLSearchParams(current); next.set('tab', value); return next })}><Icon size={18} aria-hidden="true" />{label}</button>)}</nav>
      <ProfilePanels key={user.id} active={tab} renderPanel={renderPanel} />
    </div>
    <ProfilePersonalColumn key={user.id} preferencesState={preferences} editMode={editMode && tab === 'about'} />
  </div>
}
