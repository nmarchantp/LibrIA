import { BookOpen, BrainCircuit, Library, UserRound } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLibrary } from '../context/LibraryContext'
import LibraryPage from './LibraryPage'
import InsightsPage from './InsightsPage'
import RoleManagementPanel from '../components/RoleManagementPanel'
import './ProfilePage.css'

export default function ProfilePage() {
  const { user } = useAuth()
  const { books } = useLibrary()
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = ['activity', 'library', 'analysis'].includes(requested) ? requested : 'library'
  const initials = user.display_name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('')
  return <div className="profile-page page-width"><div className="profile-banner"><BookOpen size={64} strokeWidth={1} /><span>Cada lectura cuenta algo de ti.</span></div><header className="profile-heading"><span className="profile-avatar">{initials}</span><div><span className="kicker">MI PERFIL LECTOR</span><h1>{user.display_name}</h1><p>{user.biography || 'Este es tu espacio para reunir libros, experiencias y descubrimientos.'}</p></div></header>
    <div className="profile-stats"><span><strong>{books.length}</strong> libros</span><span><strong>{books.filter(book => book.status === 'Leyendo').length}</strong> leyendo</span><span><strong>{books.filter(book => book.status === 'Terminado').length}</strong> terminados</span><small>Biblioteca de ejemplo</small></div>
    <nav className="profile-tabs" aria-label="Secciones de mi perfil">{[['library', 'Mi biblioteca', Library], ['analysis', 'Mis análisis', BrainCircuit], ['activity', 'Mi actividad', UserRound]].map(([value, label, Icon]) => <button key={value} className={tab === value ? 'active' : ''} aria-pressed={tab === value} onClick={() => setParams({ tab: value })}><Icon size={18} />{label}</button>)}</nav>
    <div className="profile-content">{tab === 'library' && <LibraryPage />}{tab === 'analysis' && <InsightsPage />}{tab === 'activity' && <section className="profile-empty"><BookOpen size={36} /><h2>Comparte tu historia lectora</h2><p>Publica reseñas y registra avances de tus libros desde la página de cada libro.</p><Link className="button primary" to="/books">Explorar libros</Link></section>}</div>
    <RoleManagementPanel user={user} />
  </div>
}
