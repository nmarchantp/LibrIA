import { useEffect, useState } from 'react'
import { ArrowUpRight, BookOpen, MessageCircle, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import { useAuth } from '../context/AuthContext'
import BookCover from '../components/BookCover'

const filters = [['all', 'Para ti'], ['reviews', 'Reseñas'], ['progress', 'Lecturas'], ['community', 'Comunidad']]

function FeedCard({ post }) {
  const { getBook } = useLibrary()
  const book = post.bookId ? getBook(post.bookId) : null
  return <article className="feed-card">
    <header className="post-author"><span className="person-avatar" style={{ background: post.color }}>{post.initials}</span><div><strong>{post.author}</strong><small>{post.role} · {post.time}</small></div><span className="post-kind">{post.type === 'reviews' ? 'Reseña' : post.type === 'progress' ? 'Avance' : 'Publicación'}</span></header>
    {post.title && <h2>{post.title}</h2>}
    {post.rating && <div className="review-rating" aria-label={post.rating + ' de 5 estrellas'}>{Array.from({ length: 5 }, (_, i) => <Star key={i} size={16} fill={i < post.rating ? 'currentColor' : 'none'} aria-hidden="true" />)}<span>{post.rating}/5</span></div>}
    <p className="post-text">{post.text}</p>
    {post.quote && <blockquote className="post-quote">“{post.quote}”<span>Desde el cuaderno de la autora</span></blockquote>}
    {book && <Link className="post-book" to={'/books/' + book.id}><BookCover book={book} /><div><small>{post.type === 'progress' ? 'CONTINÚA LEYENDO' : 'EN ESTA RESEÑA'}</small><h3>{book.title}</h3><p>{book.author}</p>{post.page && <><div className="progress-label"><span>Página {post.page} de {post.total}</span><strong>{Math.round(post.page / post.total * 100)} %</strong></div><div className="progress"><span style={{ width: post.page / post.total * 100 + '%' }} /></div></>}</div><ArrowUpRight size={18} /></Link>}
  </article>
}

export default function HomePage() {
  const [filter, setFilter] = useState('all')
  const [posts, setPosts] = useState([])
  const [feedError, setFeedError] = useState(false)
  const { books } = useLibrary()
  const { user } = useAuth()
  useEffect(() => {
    let active = true
    const refresh = () => apiRequest('/posts').then(data => {
      if (!active) return
      setFeedError(false)
      setPosts(data.map(post => ({
        id: post.id, type: post.kind, author: post.author,
        initials: post.author.split(' ').slice(0, 2).map(part => part[0]).join('').toUpperCase(),
        role: { community: 'Comunidad', reading: 'Lectura', review: 'Reseña', event: 'Evento' }[post.source], time: new Date(post.created_at).toLocaleString('es-CL'),
        title: post.title, text: post.body, color: '#e8d6ce',
      })))
    }).catch(() => { if (active) setFeedError(true) })
    refresh()
    const timer = window.setInterval(refresh, 30000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  return <div className="mural-layout">
    <section className="mural-feed" aria-labelledby="mural-title"><header className="mural-heading"><span className="kicker">TU COMUNIDAD LECTORA</span><h1 id="mural-title">Entre libros y personas.</h1><p>Descubre lo que otros leen, sienten y comparten.</p></header>
      {feedError && <div className="demo-label">No se pudieron cargar las publicaciones.</div>}
      <nav className="feed-filters" aria-label="Filtrar mural">{filters.map(([value, label]) => <button key={value} className={filter === value ? 'active' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</nav>
      <div className="feed-posts">{posts.filter(post => filter === 'all' || post.type === filter).map(post => <FeedCard key={post.id} post={post} />)}</div>
      <p className="feed-end">{posts.length ? 'Estás al día con las publicaciones.' : 'Aún no hay publicaciones.'}</p>
    </section>
    <aside className="mural-aside"><section className="reader-summary"><span className="kicker">TU RINCÓN</span><h2>Hola, {user.display_name.split(' ')[0]}</h2><p>Tu próxima página también tiene una historia.</p><Link to="/profile">Visitar mi perfil <ArrowUpRight size={16} /></Link></section>
      <section className="aside-reading"><h2><BookOpen size={18} /> Sigue leyendo</h2>{books.filter(book => book.status === 'Leyendo').map(book => <Link to={'/books/' + book.id} className="aside-book" key={book.id}><BookCover book={book} /><div><strong>{book.title}</strong><small>{book.progress}% leído · ejemplo</small></div></Link>)}<Link className="aside-link" to="/profile?tab=library">Ver mi biblioteca →</Link></section>
      <div className="community-note"><MessageCircle size={22} /><p>Un lugar para conversar sobre las historias que nos acompañan.</p><small>LibrIA · Comunidad lectora</small></div>
    </aside>
  </div>
}
