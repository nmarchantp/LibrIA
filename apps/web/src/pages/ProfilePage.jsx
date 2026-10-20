import { BookOpen, BrainCircuit, Library, Lightbulb, Palette, StickyNote, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useLibrary } from '../context/LibraryContext'
import LibraryPage from './LibraryPage'
import InsightsPage from './InsightsPage'
import AccountPage from './AccountPage'
import ProfileHeader from '../components/ProfileHeader'
import ProfilePersonalColumn from '../components/ProfilePersonalColumn'
import ThemeSelector from '../components/ThemeSelector'
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
  const { books, loading, loadError } = useLibrary()
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = ['activity', 'library', 'analysis', 'account', 'personalization'].includes(requested) ? requested : 'library'
  return <div className="profile-page page-width reader-profile">
    <div className="reader-profile-main">
      <ProfileHeader key={user.id} user={user} books={books} loading={loading} loadError={loadError} />
      <nav className="profile-tabs reader-profile-tabs" aria-label="Secciones de mi perfil">{[['library', 'Mi biblioteca', Library], ['analysis', 'Mis análisis', BrainCircuit], ['activity', 'Mi actividad', UserRound], ['account', 'Mi cuenta', UserRound], ['personalization', 'Personalización', Palette]].map(([value, label, Icon]) => <button key={value} className={tab === value ? 'active' : ''} aria-pressed={tab === value} onClick={() => setParams(current => { const next = new URLSearchParams(current); next.set('tab', value); return next })}><Icon size={18} aria-hidden="true" />{label}</button>)}</nav>
      <div className="profile-content reader-profile-content">{tab === 'library' && <LibraryPage />}{tab === 'analysis' && <InsightsPage />}{tab === 'activity' && <ProfileActivity userId={user.id} />}{tab === 'account' && <AccountPage />}{tab === 'personalization' && <ThemeSelector />}</div>
    </div>
    <ProfilePersonalColumn biography={user.biography} />
  </div>
}
