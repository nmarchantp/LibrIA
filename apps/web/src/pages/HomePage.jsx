import { useEffect, useState } from 'react'
import { ArrowUpRight, BookOpen, MessageCircle, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import { useAuth } from '../context/AuthContext'
import BookCover from '../components/BookCover'
import './HomePage.css'

const filters = [['all', 'Para ti'], ['reviews', 'Reseñas'], ['progress', 'Lecturas'], ['community', 'Comunidad']]
const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', admin: 'Admin' }
const roleColors = { lector: '#e8d6ce', influencer: '#dce5d8', autor: '#e7dfed', libreria: '#eedebc', admin: '#d5e3e8' }
const composerCopy = {
  influencer: { heading: 'Comparte con tu comunidad', hint: 'Publica recomendaciones, lecturas conjuntas o conversaciones sobre libros.', placeholder: '¿Qué recomendarías hoy?' },
  autor: { heading: 'Comparte tu trabajo', hint: 'Publica novedades de tus obras o anuncia un encuentro con lectores.', placeholder: '¿Qué hay de nuevo en tu escritura?' },
  libreria: { heading: 'Publica desde tu librería', hint: 'Comparte promociones, novedades o un evento de tu librería.', placeholder: 'Cuéntale a la comunidad sobre tus libros o actividades.' },
  admin: { heading: 'Publica como administrador', hint: 'Comparte anuncios y eventos para la comunidad.', placeholder: 'Escribe un anuncio para la comunidad.' },
}

function PostComposer({ role, onCreated }) {
  const { retry } = useAuth()
  const copy = composerCopy[role]
  const [source, setSource] = useState('community')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async event => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const token = localStorage.getItem('libria_token')
      await apiRequest('/posts', { method: 'POST', headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ source, kind: 'community', title: title.trim() || null, body: body.trim() }) })
      setTitle('')
      setBody('')
      onCreated()
    } catch (cause) {
      if (cause.status === 403) retry()
      setError(cause.status === 403 ? 'Tu perfil ya no tiene permiso para este tipo de publicación.' : 'No se pudo publicar. Inténtalo de nuevo.')
    } finally {
      setBusy(false)
    }
  }
  return <form className="post-composer" onSubmit={submit}>
    <h2>{copy.heading}</h2><p className="composer-hint">{copy.hint}</p>
    {(role === 'autor' || role === 'libreria' || role === 'admin') && <label>Tipo<select value={source} onChange={event => setSource(event.target.value)}><option value="community">{role === 'libreria' ? 'Publicación o promoción' : 'Publicación'}</option><option value="event">Evento</option></select></label>}
    <label>Título<input value={title} onChange={event => setTitle(event.target.value)} maxLength="200" placeholder="Título opcional" /></label>
    <label>Contenido<textarea value={body} onChange={event => setBody(event.target.value)} maxLength="3000" rows="3" required placeholder={copy.placeholder} /></label>
    {error && <p className="comment-error" role="alert">{error}</p>}
    <button className="button primary" disabled={busy || !body.trim()}>{busy ? 'Publicando...' : 'Publicar'}</button>
  </form>
}

function FeedCard({ post }) {
  const { getBook } = useLibrary()
  const book = post.bookId ? getBook(post.bookId) : null
  const [commentsOpen, setCommentsOpen] = useState(false)
  const [comments, setComments] = useState([])
  const [commentText, setCommentText] = useState('')
  const [commentsLoading, setCommentsLoading] = useState(false)
  const [commentSending, setCommentSending] = useState(false)
  const [commentError, setCommentError] = useState('')

  const toggleComments = async () => {
    if (commentsOpen) { setCommentsOpen(false); return }
    setCommentsOpen(true)
    setCommentsLoading(true)
    setCommentError('')
    try {
      setComments(await apiRequest(`/posts/${post.id}/comments`))
    } catch {
      setCommentError('No se pudieron cargar los comentarios. Cierra y vuelve a abrir esta sección para reintentar.')
    } finally {
      setCommentsLoading(false)
    }
  }

  const submitComment = async event => {
    event.preventDefault()
    const body = commentText.trim()
    if (!body || commentSending) return
    const token = localStorage.getItem('libria_token')
    if (!token) { setCommentError('Tu sesión terminó. Vuelve a iniciar sesión para comentar.'); return }
    setCommentSending(true)
    setCommentError('')
    try {
      const comment = await apiRequest(`/posts/${post.id}/comments`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ body }),
      })
      setComments(current => [...current, comment])
      setCommentText('')
    } catch (error) {
      setCommentError(error.status === 401 ? 'Tu sesión terminó. Vuelve a iniciar sesión para comentar.' : 'No se pudo publicar el comentario. Inténtalo de nuevo.')
    } finally {
      setCommentSending(false)
    }
  }

  return <article className="feed-card">
    <header className="post-author"><span className="person-avatar" style={{ background: post.color }}>{post.initials}</span><div className="post-person"><div className="post-person-name"><strong>{post.author}</strong><span className={`user-role-badge role-${post.authorRole}`}>{roleLabels[post.authorRole] || 'Lector'}</span></div><small>{post.time}</small></div><span className="post-kind">{post.source === 'event' ? 'Evento' : post.type === 'reviews' ? 'Reseña' : post.type === 'progress' ? 'Avance' : 'Publicación'}</span></header>
    {post.title && <h2>{post.title}</h2>}
    {post.rating && <div className="review-rating" aria-label={post.rating + ' de 5 estrellas'}>{Array.from({ length: 5 }, (_, i) => <Star key={i} size={16} fill={i < post.rating ? 'currentColor' : 'none'} aria-hidden="true" />)}<span>{post.rating}/5</span></div>}
    {post.bookTitle && !post.title && <h2>{post.bookTitle}</h2>}
    <p className="post-text">{post.text}</p>
    {post.type === 'progress' && post.progressPercent !== null && <div className="progress-label"><span>Progreso de lectura</span><strong>{post.progressPercent} %</strong></div>}
    {post.quote && <blockquote className="post-quote">“{post.quote}”<span>Desde el cuaderno de la autora</span></blockquote>}
    {book && <Link className="post-book" to={'/books/' + book.id}><BookCover book={book} /><div><small>{post.type === 'progress' ? 'CONTINÚA LEYENDO' : 'EN ESTA RESEÑA'}</small><h3>{book.title}</h3><p>{book.author}</p>{post.page && <><div className="progress-label"><span>Página {post.page} de {post.total}</span><strong>{Math.round(post.page / post.total * 100)} %</strong></div><div className="progress"><span style={{ width: post.page / post.total * 100 + '%' }} /></div></>}</div><ArrowUpRight size={18} /></Link>}
    <section className="post-comments" aria-label={`Comentarios de ${post.title || post.author}`}>
      <button type="button" className="comments-toggle" aria-expanded={commentsOpen} aria-controls={`comments-${post.id}`} onClick={toggleComments}>
        <MessageCircle size={17} aria-hidden="true" /> {commentsOpen ? 'Ocultar comentarios' : 'Ver comentarios'}
      </button>
      {commentsOpen && <div id={`comments-${post.id}`} className="comments-panel">
        {commentsLoading ? <p className="comments-state">Cargando comentarios...</p> : <>
          <div className="comments-list" aria-live="polite">
            {comments.length === 0 && !commentError && <p className="comments-state">Sé la primera persona en comentar.</p>}
            {comments.map(comment => <div className="comment-item" key={comment.id}>
              <div className="comment-meta"><div className="comment-author"><strong>{comment.author}</strong><span className={`user-role-badge role-${comment.author_role}`}>{roleLabels[comment.author_role] || 'Lector'}</span></div><time dateTime={comment.created_at}>{new Date(comment.created_at).toLocaleString('es-CL')}</time></div>
              <p>{comment.body}</p>
            </div>)}
          </div>
          <form className="comment-form" onSubmit={submitComment}>
            <label htmlFor={`comment-${post.id}`}>Escribe un comentario</label>
            <textarea id={`comment-${post.id}`} value={commentText} onChange={event => setCommentText(event.target.value)} maxLength={1000} rows={3} required placeholder="Comparte tu opinión..." />
            {commentError && <p className="comment-error" role="alert">{commentError}</p>}
            <button type="submit" className="button primary" disabled={commentSending || !commentText.trim()}>{commentSending ? 'Publicando...' : 'Publicar comentario'}</button>
          </form>
        </>}
      </div>}
    </section>
  </article>
}

export default function HomePage() {
  const [filter, setFilter] = useState('all')
  const [posts, setPosts] = useState([])
  const [feedError, setFeedError] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const { books } = useLibrary()
  const { user } = useAuth()
  useEffect(() => {
    let active = true
    const refresh = () => apiRequest('/posts').then(data => {
      if (!active) return
      setFeedError(false)
      setPosts(data.map(post => ({
        id: post.id, type: post.kind, author: post.author, authorRole: post.author_role,
        initials: post.author.split(' ').slice(0, 2).map(part => part[0]).join('').toUpperCase(),
        time: new Date(post.created_at).toLocaleString('es-CL'),
        title: post.title, text: post.body, source: post.source, bookId: post.book_ref,
        bookTitle: post.book_title, rating: post.rating, progressPercent: post.progress_percent,
        color: roleColors[post.author_role] || roleColors.lector,
      })))
    }).catch(() => { if (active) setFeedError(true) })
    refresh()
    const timer = window.setInterval(refresh, 30000)
    return () => { active = false; window.clearInterval(timer) }
  }, [refreshKey])
  return <div className="mural-layout">
    <section className="mural-feed" aria-labelledby="mural-title"><header className="mural-heading"><span className="kicker">TU COMUNIDAD LECTORA</span><h1 id="mural-title">Entre libros y personas.</h1><p>Descubre lo que otros leen, sienten y comparten.</p></header>
      {user.role !== 'lector' && <PostComposer role={user.role} onCreated={() => setRefreshKey(current => current + 1)} />}
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
