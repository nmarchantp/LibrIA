import { useEffect, useState } from 'react'
import { ArrowUpRight, BookOpen, Heart, MessageCircle, Star, UserRoundCheck, UserRoundPlus, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest, apiUrl } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import { useAuth } from '../context/AuthContext'
import BookCover from '../components/BookCover'
import './HomePage.css'

const filters = [['all', 'Para ti'], ['reviews', 'Reseñas'], ['progress', 'Lecturas'], ['community', 'Comunidad']]
const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', editorial: 'Editorial', admin: 'Admin' }
const roleColors = { lector: '#e8d6ce', influencer: '#dce5d8', autor: '#e7dfed', libreria: '#eedebc', editorial: '#d5e3e8', admin: '#d5e3e8' }
const composerCopy = {
  influencer: { heading: 'Comparte con tu comunidad', hint: 'Publica recomendaciones, lecturas conjuntas o conversaciones sobre libros.', placeholder: '¿Qué recomendarías hoy?' },
  autor: { heading: 'Comparte tu trabajo', hint: 'Publica novedades de tus obras o anuncia un encuentro con lectores.', placeholder: '¿Qué hay de nuevo en tu escritura?' },
  libreria: { heading: 'Publica desde tu librería', hint: 'Comparte promociones, novedades o un evento de tu librería.', placeholder: 'Cuéntale a la comunidad sobre tus libros o actividades.' },
  editorial: { heading: 'Publica desde tu editorial', hint: 'Comparte novedades, promociones y eventos.', placeholder: 'Escribe una novedad editorial.' },
  admin: { heading: 'Publica como administrador', hint: 'Comparte anuncios y eventos para la comunidad.', placeholder: 'Escribe un anuncio para la comunidad.' },
}

function PostComposer({ role, profileId, onCreated }) {
  const { retry } = useAuth()
  const copy = composerCopy[role]
  const [source, setSource] = useState('community')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [images, setImages] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [imageError, setImageError] = useState('')
  const selectImages = event => {
    const selected = Array.from(event.target.files || [])
    const totalSize = selected.reduce((sum, image) => sum + image.size, 0)
    if (selected.length > 10) setImageError('Puedes adjuntar hasta 10 imágenes.')
    else if (selected.some(image => !['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(image.type))) setImageError('Usa imágenes JPEG, PNG, GIF o WebP.')
    else if (selected.some(image => image.size > 5 * 1024 * 1024) || totalSize > 25 * 1024 * 1024) setImageError('Cada imagen puede pesar hasta 5 MB y el total hasta 25 MB.')
    else { setImages(selected); setImageError('') }
    event.target.value = ''
  }
  const submit = async event => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const token = localStorage.getItem('libria_token')
      const form = new FormData()
      const publication = { source: source === 'event' ? 'event' : 'community', publication_type: source === 'community' ? 'free' : source,
        author_profile_id: profileId, kind: 'community', title: title.trim(), body: body.trim() }
      Object.entries(publication).forEach(([key, value]) => form.append(key, value))
      images.forEach(image => form.append('images', image))
      await apiRequest('/posts', { method: 'POST', headers: { Authorization: `Bearer ${token}` },
        body: form })
      setTitle('')
      setBody('')
      setImages([])
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
    <label>Tipo<select value={source} onChange={event => setSource(event.target.value)}><option value="community">Publicación</option><option value="event">Evento</option><option value="promotion">Promoción</option></select></label>
    <label>Título<input value={title} onChange={event => setTitle(event.target.value)} maxLength="200" placeholder="Título opcional" /></label>
    <label>Comentario breve (máximo 500 caracteres)<textarea value={body} onChange={event => setBody(event.target.value)} maxLength="500" rows="3" required placeholder={copy.placeholder} /></label>
    <small className="composer-counter">{body.length}/500</small>
    <label>Imágenes (hasta 10)<input type="file" accept="image/jpeg,image/png,image/gif,image/webp" multiple onChange={selectImages} /></label>
    {images.length > 0 && <ul className="selected-images">{images.map((image, index) => <li key={`${image.name}-${index}`}><span>{image.name}</span><button type="button" aria-label={`Quitar ${image.name}`} onClick={() => setImages(current => current.filter((_, itemIndex) => itemIndex !== index))}><X size={15} /></button></li>)}</ul>}
    {imageError && <p className="comment-error" role="alert">{imageError}</p>}
    {error && <p className="comment-error" role="alert">{error}</p>}
    <button className="button primary" disabled={busy || !body.trim() || Boolean(imageError)}>{busy ? 'Publicando...' : 'Publicar'}</button>
  </form>
}

function FeedCard({ post }) {
  const { getBook } = useLibrary()
  const book = post.bookId ? getBook(post.bookId) : null
  const [liked, setLiked] = useState(post.likedByMe)
  const [likeCount, setLikeCount] = useState(post.likeCount)
  const [following, setFollowing] = useState(post.followingAuthor)
  const [interactionBusy, setInteractionBusy] = useState(false)
  const [interactionError, setInteractionError] = useState('')
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

  const toggleLike = async () => {
    const token = localStorage.getItem('libria_token')
    if (!token || interactionBusy) { setInteractionError('Inicia sesión para indicar que te gusta.'); return }
    setInteractionBusy(true)
    setInteractionError('')
    try {
      const result = await apiRequest(`/posts/${post.id}/like`, {
        method: liked ? 'DELETE' : 'PUT', headers: { Authorization: 'Bearer ' + token },
      })
      setLiked(result.liked_by_me)
      setLikeCount(result.like_count)
    } catch {
      setInteractionError('No se pudo actualizar tu me gusta. Inténtalo de nuevo.')
    } finally {
      setInteractionBusy(false)
    }
  }

  const toggleFollow = async () => {
    const token = localStorage.getItem('libria_token')
    if (!token || interactionBusy) { setInteractionError('Inicia sesión para seguir este perfil.'); return }
    setInteractionBusy(true)
    setInteractionError('')
    try {
      if (following) await apiRequest(`/profiles/${post.authorProfileId}/follow`, {
        method: 'DELETE', headers: { Authorization: 'Bearer ' + token },
      })
      else await apiRequest(`/profiles/${post.authorProfileId}/follow`, {
        method: 'POST', headers: { Authorization: 'Bearer ' + token },
      })
      setFollowing(!following)
    } catch {
      setInteractionError('No se pudo actualizar el seguimiento. Inténtalo de nuevo.')
    } finally {
      setInteractionBusy(false)
    }
  }

  return <article className="feed-card">
    <header className="post-author"><span className="person-avatar" style={{ background: post.color }}>{post.initials}</span><div className="post-person"><div className="post-person-name"><strong>{post.author}</strong><span className={`user-role-badge role-${post.authorRole}`}>{roleLabels[post.authorRole] || 'Lector'}</span></div><small>{post.time}</small></div><span className="post-kind">{post.source === 'event' ? 'Evento' : post.type === 'reviews' ? 'Reseña' : post.type === 'progress' ? 'Avance' : 'Publicación'}</span></header>
    {post.title && <h2>{post.title}</h2>}
    {post.rating && <div className="review-rating" aria-label={post.rating + ' de 5 estrellas'}>{Array.from({ length: 5 }, (_, i) => <Star key={i} size={16} fill={i < post.rating ? 'currentColor' : 'none'} aria-hidden="true" />)}<span>{post.rating}/5</span></div>}
    {post.bookTitle && !post.title && <h2>{post.bookTitle}</h2>}
    <p className="post-text">{post.text}</p>
    {post.images.length > 0 && <div className="post-images">{post.images.map(image => <img key={image} src={apiUrl(image)} alt={`Imagen de la publicación de ${post.author}`} loading="lazy" />)}</div>}
    {post.type === 'progress' && post.progressPercent !== null && <div className="progress-label"><span>Progreso de lectura</span><strong>{post.progressPercent} %</strong></div>}
    {post.quote && <blockquote className="post-quote">“{post.quote}”<span>Desde el cuaderno de la autora</span></blockquote>}
    {book && <Link className="post-book" to={'/books/' + book.id}><BookCover book={book} /><div><small>{post.type === 'progress' ? 'CONTINÚA LEYENDO' : 'EN ESTA RESEÑA'}</small><h3>{book.title}</h3><p>{book.author}</p>{post.page && <><div className="progress-label"><span>Página {post.page} de {post.total}</span><strong>{Math.round(post.page / post.total * 100)} %</strong></div><div className="progress"><span style={{ width: post.page / post.total * 100 + '%' }} /></div></>}</div><ArrowUpRight size={18} /></Link>}
    {post.feedItemType !== 'reading_event' && <div className="post-actions">
      <button type="button" aria-pressed={liked} disabled={interactionBusy} onClick={toggleLike}><Heart size={17} fill={liked ? 'currentColor' : 'none'} /> Me gusta <span>{likeCount}</span></button>
      {post.authorProfileId && <button type="button" aria-pressed={following} disabled={interactionBusy} onClick={toggleFollow}>{following ? <UserRoundCheck size={17} /> : <UserRoundPlus size={17} />}{following ? 'Siguiendo' : 'Seguir perfil'}</button>}
      {interactionError && <p className="comment-error" role="alert">{interactionError}</p>}
    </div>}
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
  const [profiles, setProfiles] = useState([])
  const [profileId, setProfileId] = useState('')
  const [profileError, setProfileError] = useState(false)
  useEffect(() => {
    let active = true
    apiRequest('/profiles/me', { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` } })
      .then(data => { if (active) { setProfiles(data); setProfileError(false) } })
      .catch(() => { if (active) setProfileError(true) })
    return () => { active = false }
  }, [user.id, refreshKey])
  const publishingProfiles = profiles.filter(profile => profile.kind === 'organization' || profile.capabilities.some(capability => ['autor', 'influencer'].includes(capability)) || (user.role === 'admin' && profile.kind === 'personal'))
  const selectedProfile = publishingProfiles.find(profile => profile.id === profileId) || publishingProfiles[0]
  const publishingRole = selectedProfile?.organization_type || (user.role === 'admin' ? 'admin' : selectedProfile?.capabilities.includes('autor') ? 'autor' : 'influencer')
  useEffect(() => {
    let active = true
    const refresh = () => {
      const token = localStorage.getItem('libria_token')
      const headers = token ? { Authorization: 'Bearer ' + token } : {}
      return apiRequest('/posts', { headers }).then(data => {
        if (!active) return
        setFeedError(false)
        setPosts(data.map(post => ({
          id: post.id, type: post.kind, feedItemType: post.feed_item_type, authorProfileId: post.author_profile_id,
          images: post.images || [], likeCount: post.like_count || 0, likedByMe: post.liked_by_me || false,
          followingAuthor: post.following_author || false, author: post.author, authorRole: post.author_role,
          initials: post.author.split(' ').slice(0, 2).map(part => part[0]).join('').toUpperCase(),
          time: new Date(post.created_at).toLocaleString('es-CL'),
          title: post.title, text: post.body, source: post.source, bookId: post.book_ref,
          bookTitle: post.book_title, rating: post.rating, progressPercent: post.progress_percent,
          color: roleColors[post.author_role] || roleColors.lector,
        })))
      }).catch(() => { if (active) setFeedError(true) })
    }
    refresh()
    const timer = window.setInterval(refresh, 30000)
    return () => { active = false; window.clearInterval(timer) }
  }, [refreshKey])
  return <div className="mural-layout">
    <section className="mural-feed" aria-labelledby="mural-title"><header className="mural-heading"><span className="kicker">TU COMUNIDAD LECTORA</span><h1 id="mural-title">Entre libros y personas.</h1><p>Descubre lo que otros leen, sienten y comparten.</p></header>
      {profileError && <p role="alert">No se pudieron cargar tus permisos de publicación.</p>}
      {publishingProfiles.length > 1 && <label>Publicar como<select value={selectedProfile?.id || ''} onChange={event => setProfileId(event.target.value)}>{publishingProfiles.map(profile => <option key={profile.id} value={profile.id}>{profile.display_name}</option>)}</select></label>}
      {selectedProfile && <PostComposer key={selectedProfile.id} role={publishingRole} profileId={selectedProfile.id} onCreated={() => setRefreshKey(current => current + 1)} />}
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
