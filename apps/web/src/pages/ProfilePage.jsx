import { BookOpen, BrainCircuit, Library, Lightbulb, StickyNote, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useLibrary } from '../context/LibraryContext'
import LibraryPage from './LibraryPage'
import InsightsPage from './InsightsPage'
import RoleManagementPanel from '../components/RoleManagementPanel'
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
  const { books } = useLibrary()
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = ['activity', 'library', 'analysis'].includes(requested) ? requested : 'library'
  const initials = user.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')
  return <div className="profile-page page-width"><div className="profile-banner"><BookOpen size={64} strokeWidth={1} /><span>Cada lectura cuenta algo de ti.</span></div><header className="profile-heading"><span className="profile-avatar">{initials}</span><div><span className="kicker">MI PERFIL</span><h1>{user.display_name}</h1><p>{user.biography || 'Este es tu espacio para reunir libros, experiencias y descubrimientos.'}</p></div></header>
    <div className="profile-stats"><span><strong>{books.length}</strong> libros</span><span><strong>{books.filter(book => book.status === 'Leyendo').length}</strong> leyendo</span><span><strong>{books.filter(book => book.status === 'Terminado').length}</strong> terminados</span><small>Biblioteca de ejemplo</small></div>
    <nav className="profile-tabs" aria-label="Secciones de mi perfil">{[['library', 'Mi biblioteca', Library], ['analysis', 'Mis análisis', BrainCircuit], ['activity', 'Mi actividad', UserRound]].map(([value, label, Icon]) => <button key={value} className={tab === value ? 'active' : ''} aria-pressed={tab === value} onClick={() => setParams({ tab: value })}><Icon size={18} />{label}</button>)}</nav>
    <div className="profile-content">{tab === 'library' && <LibraryPage />}{tab === 'analysis' && <InsightsPage />}{tab === 'activity' && <ProfileActivity userId={user.id} />}</div>
    <RoleManagementPanel user={user} />
  </div>
}
