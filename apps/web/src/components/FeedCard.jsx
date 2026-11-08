import RatingStar from './RatingStar'
import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, BookOpen, Eye, Heart, MessageCircle, Pencil, Send, UserRoundCheck, UserRoundPlus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest, apiUrl } from '../api/client'
import { useLibrary } from '../context/LibraryContext'
import { useAuth } from '../context/AuthContext'
import BookCover from './BookCover'
import SpoilerShield from './SpoilerShield'
import FormattedText from './FormattedText'
import MuralEventContent from './MuralEventContent'
import PostGallery from './PostGallery'
import ActivityOptionsMenu from './ActivityOptionsMenu'
import CommentEntry from './CommentEntry'
import { EventAttendanceButton,EventAttendanceCount } from './EventPresentation'
import { useMuralManagement } from '../context/MuralManagementContext'
import '../pages/HomePage.css'

const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', editorial: 'Editorial', admin: 'Admin' }
const publicationLabels = { news: 'Anuncio', promotion: 'Promoción', launch: 'Lanzamiento', institutional: 'Institucional', event: 'Evento', note: 'Nota', theory: 'Teoría' }
// Matches CommentCreate.body in the existing backend schema.
const COMMENT_LIMIT = 1000
const initialsFor = name => (name || '').split(' ').filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase()
const imageUrl = value => /^https?:\/\//i.test(value) ? value : apiUrl(value)
function ProgressBookCover({ book }) {
  const [failed, setFailed] = useState(false)
  return <div className="book-cover" style={{ background: book.color || 'var(--soft)', color: book.accent || 'var(--ink)' }} aria-label={`Portada de ${book.title}`}>
    {book.image && !failed ? <img className="book-cover-image" src={book.image} alt="" onError={() => setFailed(true)} /> : <span className="cover-mark" aria-hidden="true"><BookOpen size={25} strokeWidth={1.3} /></span>}
  </div>
}
export default function FeedCard({ post, interactions, initialCommentsOpen = false, socialDialog = false, widePublication = false }) {
  const { getBook } = useLibrary()
  const { user } = useAuth()
  const management=useMuralManagement()
  const [customCover,setCustomCover] = useState(post.customBookCoverUrl || null)
  useEffect(()=>setCustomCover(post.customBookCoverUrl || null),[post.customBookCoverUrl])
  const libraryBook = post.bookId ? getBook(post.bookId) : null
  const book = post.bookTitle ? {
    ...libraryBook,
    id: post.bookId,
    title: post.bookTitle,
    author: post.bookAuthor || libraryBook?.author || '',
    image: customCover || post.bookCoverUrl || libraryBook?.image,
    initial: post.bookTitle.charAt(0),
    color: 'var(--lavender-soft)',
    accent: 'var(--ink)',
  } : libraryBook
  const BookContainer = book?.id ? Link : 'div'
  const [localLiked, setLiked] = useState(post.likedByMe)
  const [localLikeCount, setLikeCount] = useState(post.likeCount)
  const [following, setFollowing] = useState(post.followingAuthor)
  const [interactionBusy, setInteractionBusy] = useState(false)
  const [interactionError, setInteractionError] = useState('')
  const [commentsOpen, setCommentsOpen] = useState(initialCommentsOpen || socialDialog)
  const [localComments, setComments] = useState([])
  const comments=interactions?.commentItems??localComments
  const [commentText, setCommentText] = useState('')
  const [commentsLoading, setCommentsLoading] = useState(initialCommentsOpen || socialDialog)
  const [commentSending, setCommentSending] = useState(false)
  const [commentError, setCommentError] = useState('')
  const wordLimited = socialDialog && post.feedItemType === 'reading_event'
  const commentWords = commentText.trim() ? commentText.trim().split(/\s+/u).length : 0
  const commentTooLong = wordLimited ? commentWords > 200 : commentText.length > COMMENT_LIMIT
  const commentsPanel = useRef(null)
  const commentInput = useRef(null)
  const positionedComments = useRef(false)
  const commentList = useRef(null)
  const sendingComment = useRef(false)
  const revealNewComment = useRef(false)

  useEffect(() => {
    if (!socialDialog || !commentInput.current) return
    const input = commentInput.current
    input.style.height = 'auto'
    input.style.height = `${Math.min(input.scrollHeight, 144)}px`
  }, [socialDialog, commentText, commentsLoading])

  useEffect(() => {
    if (!revealNewComment.current) return
    const list = commentList.current
    if (list) list.scrollTop = list.scrollHeight
    revealNewComment.current = false
  }, [comments])

  useEffect(() => {
    if (!initialCommentsOpen || commentsLoading || positionedComments.current) return
    const frame = requestAnimationFrame(() => {
      commentsPanel.current?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
      // Only an explicit comment intent focuses the composer, including on mobile.
      commentInput.current?.focus({ preventScroll: true })
      positionedComments.current = true
    })
    return () => cancelAnimationFrame(frame)
  }, [initialCommentsOpen, commentsLoading])

  const liked = interactions ? interactions.liked_by_me : localLiked
  const likeCount = interactions ? interactions.like_count : localLikeCount
  const socialRef = useRef(interactions)
  socialRef.current = interactions
  useEffect(() => {
    if (!initialCommentsOpen && !socialDialog) return
    const controller = new AbortController()
    let active = true
    const request = socialRef.current ? socialRef.current.loadComments(controller.signal) : apiRequest(`/posts/${post.id}/comments`, { signal: controller.signal })
    request.then(items => { if (active) setComments(items) })
      .catch(() => { if (active) setCommentError('No se pudieron cargar los comentarios.') })
      .finally(() => { if (active) setCommentsLoading(false) })
    return () => { active = false; controller.abort() }
  }, [initialCommentsOpen, socialDialog, post.id])

  const toggleComments = async () => {
    if (commentsOpen) { setCommentsOpen(false); return }
    setCommentsOpen(true)
    setCommentsLoading(true)
    setCommentError('')
    try {
      if (interactions) {
        if (!await interactions.view('open_comments')) throw new Error('Actividad no disponible')
        setComments(await interactions.loadComments())
      } else setComments(await apiRequest(`/posts/${post.id}/comments`))
    } catch {
      setCommentError('No se pudieron cargar los comentarios. Cierra y vuelve a abrir esta sección para reintentar.')
    } finally {
      setCommentsLoading(false)
    }
  }

  const submitComment = async event => {
    event.preventDefault()
    const body = commentText.trim()
    if (!body || commentTooLong || sendingComment.current) return
    const token = localStorage.getItem('libria_token')
    if (!token) { setCommentError('Tu sesión terminó. Vuelve a iniciar sesión para comentar.'); return }
    sendingComment.current = true
    setCommentSending(true)
    setCommentError('')
    revealNewComment.current = true
    try {
      const comment = interactions ? await interactions.addComment(body) : await apiRequest(`/posts/${post.id}/comments`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: JSON.stringify({ body }),
      })
      setComments(current => [...current, comment])
      setCommentText('')
    } catch (error) {
      revealNewComment.current = false
      setCommentError(error.status === 401 ? 'Tu sesión terminó. Vuelve a iniciar sesión para comentar.' : 'No se pudo publicar el comentario. Inténtalo de nuevo.')
    } finally {
      sendingComment.current = false
      setCommentSending(false)
    }
  }

  const toggleLike = async () => {
    if (interactions) { await interactions.toggleLike(); return }
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

  const isProgress = post.type === 'progress'
  const isEventPublication=post.feedItemType==='publication'&&(post.publicationType==='event'||post.source==='event')
  const progressText = isProgress && book?.title
    ? (post.text || '').replaceAll(`de "${book.title}"`, 'de su lectura').replaceAll(`"${book.title}"`, 'este libro')
    : post.text
  const progressMessage = <><FormattedText className="post-text" text={progressText} /><PostGallery images={post.images.map(imageUrl)} alt={`Imagen de la lectura de ${post.author}`} /></>

  const followControl = post.authorProfileId && <button type="button" className={socialDialog || widePublication ? "mural-follow-button" : undefined} aria-label={following ? "Dejar de seguir perfil" : "Seguir perfil"} title={following ? "Dejar de seguir perfil" : "Seguir perfil"} aria-pressed={following} disabled={interactionBusy} onClick={toggleFollow}>{following ? <UserRoundCheck size={17} /> : <UserRoundPlus size={17} />}{!socialDialog && !widePublication && (following ? 'Siguiendo' : 'Seguir perfil')}</button>
  const focusComment = () => {
    commentInput.current?.scrollIntoView({ block: 'nearest' })
    commentInput.current?.focus({ preventScroll: true })
  }
  const openImage = widePublication ? () => interactions.view('open') : undefined
  return <article className={`feed-card${isProgress ? ' feed-card-progress' : ''}${socialDialog ? ' feed-card-social-dialog' : ''}${widePublication ? ' mural-publication' : ''}${widePublication&&isEventPublication ? ' mural-publication-event' : ''}`}>
    <header className="post-author"><span className="person-avatar" style={{ background: post.color }}>{post.avatarUrl ? <img src={post.avatarUrl} alt="" /> : post.initials}</span><div className="post-person"><div className="post-person-name"><strong>{post.author}</strong><span className={`user-role-badge role-${post.authorRole}`}>{roleLabels[post.authorRole] || 'Lector'}</span></div><small>{post.time}</small></div>{isEventPublication&&(socialDialog||widePublication)?<><EventAttendanceButton details={post.eventDetails} showCount={false} />{post.activity?.can_manage&&management&&<button type="button" className="event-edit-button" aria-label="Editar evento" title="Editar evento" onClick={()=>management.edit(post.activity)}><Pencil size={20} /></button>}</>:<><span className="post-kind">{publicationLabels[post.publicationType] || (post.source === 'event' ? 'Evento' : post.type === 'reviews' ? 'Reseña' : post.type === 'progress' ? ({ start: 'Nueva lectura', finish: 'Terminado' }[post.readingEvent] || 'Avance') : 'Publicación')}</span>{(socialDialog || widePublication) && followControl && <span className="mural-user-follow">{followControl}</span>}<ActivityOptionsMenu item={post.activity} /></>}</header>
    <div className={widePublication ? `mural-publication-editorial${book ? ' has-related-book' : ''}` : 'feed-content-pass-through'}>
    <div className={widePublication ? 'mural-publication-content' : 'feed-content-pass-through'}>
    {widePublication&&isEventPublication?<MuralEventContent key={`${post.id}:${post.text}`} post={post} onOpen={openImage} />:isProgress || socialDialog ? <div className="post-reading-progress">
      {book && <BookContainer className="post-progress-cover" {...(book.id ? { to: '/books/' + book.id, 'aria-label': `Ver ficha de ${book.title}` } : {})}><ProgressBookCover key={book.image || book.id} book={book} /></BookContainer>}
      <div className="post-progress-details">
        {book && <><h3 className="post-progress-title">{book.title}</h3>{book.author && <p className="post-progress-author">{book.author}</p>}</>}
        {socialDialog && post.title && post.title !== book?.title && <h3 className="post-activity-title">{post.title}</h3>}
        {socialDialog && post.rating != null && <div className="review-rating" aria-label={post.rating + ' de 5 estrellas'}>{Array.from({ length: 5 }, (_, i) => <RatingStar key={i} size={16} fraction={post.rating - i} />)}<span>{post.rating}/5</span></div>}
        {post.isSpoiler ? <SpoilerShield>{progressMessage}</SpoilerShield> : progressMessage}
        {socialDialog && post.quote && <blockquote className="post-quote">“{post.quote}”<span>Desde el cuaderno de la autora</span></blockquote>}
        {post.progressPercent != null && <div className="post-progress-meter"><progress max="100" value={post.progressPercent} aria-label="Progreso de lectura" /><strong>{post.progressPercent} %</strong></div>}
        {book?.id && <Link className="post-progress-book-link" to={'/books/' + book.id}>Ver ficha del libro <ArrowUpRight size={14} aria-hidden="true" /></Link>}
      </div>
    </div> : <>
    {post.title && <h2>{post.title}</h2>}
    {post.rating && <div className="review-rating" aria-label={post.rating + ' de 5 estrellas'}>{Array.from({ length: 5 }, (_, i) => <RatingStar key={i} size={16} fraction={post.rating - i} />)}<span>{post.rating}/5</span></div>}
    {post.bookTitle && !post.title && <h2>{post.bookTitle}</h2>}
    {post.isSpoiler ? <SpoilerShield><FormattedText className="post-text" text={post.text} /><PostGallery images={post.images.map(imageUrl)} alt={`Imagen de la reseña de ${post.author}`} onOpen={openImage} editorial={widePublication} /></SpoilerShield> : <><FormattedText className="post-text" text={post.text} />
    <PostGallery images={post.images.map(imageUrl)} alt={`Imagen de la publicación de ${post.author}`} onOpen={openImage} editorial={widePublication} /></>}

    {post.quote && <blockquote className="post-quote">“{post.quote}”<span>Desde el cuaderno de la autora</span></blockquote>}
    {book && !widePublication && <BookContainer className="post-book" {...(book.id ? { to: '/books/' + book.id } : {})}><BookCover book={book} /><div><small>{post.type === 'progress' ? 'LECTURA COMPARTIDA' : post.type === 'reviews' ? 'EN ESTA RESEÑA' : 'OBRA ENLAZADA'}</small><h3>{book.title}</h3>{book.author && <p>{book.author}</p>}{post.progressPercent !== null && post.type === 'progress' && <div className="progress"><span style={{ width: post.progressPercent + '%' }} /></div>}</div>{book.id && <ArrowUpRight size={18} />}</BookContainer>}
    </>}
    </div>
    {widePublication && book && <aside className="mural-related-book" aria-label="Obra relacionada"><h3 className="mural-related-label"><BookOpen size={20} aria-hidden="true" />Obra relacionada</h3><BookContainer className="post-book" {...(book.id ? { to: '/books/' + book.id } : {})}><BookCover book={book} /><div><h3>{book.title}</h3>{book.author && <p>{book.author}</p>}</div></BookContainer></aside>}
    </div>
    {(interactions?.capabilities.can_like || post.feedItemType !== 'reading_event') && <div className="post-actions">
      <button type="button" aria-pressed={liked} disabled={interactionBusy || interactions?.likeBusy} onClick={event => { event.stopPropagation(); toggleLike() }}><Heart size={17} fill={liked ? 'currentColor' : 'none'} /> Me gusta <span>{likeCount}</span></button>
      {socialDialog || widePublication ? <><button type="button" onClick={event => { event.stopPropagation(); if (widePublication) toggleComments(); else focusComment() }} aria-expanded={widePublication ? commentsOpen : undefined} aria-controls={`comments-${post.id}`} aria-label={widePublication ? 'Abrir comentarios' : 'Ir a los comentarios'}><MessageCircle size={17} aria-hidden="true" /> Comentarios <span>{interactions?.comment_count ?? '—'}</span></button>{isEventPublication&&<EventAttendanceCount details={post.eventDetails} />}{post.feedItemType !== 'reading_event' && <span className="mural-dialog-views" aria-label={`${interactions?.view_count ?? '—'} visualizaciones`}><Eye size={17} aria-hidden="true" /><span>{interactions?.view_count ?? '—'}</span></span>}</> : followControl}
      {(interactionError || interactions?.error) && <p className="comment-error" role="alert">{interactionError || interactions.error}</p>}
    </div>}
    {(!widePublication || commentsOpen) && <section className="post-comments" aria-label={`Comentarios de ${post.title || post.author}`}>
      {socialDialog || widePublication ? <div className="mural-comments-heading"><h3>Comentarios</h3><span aria-label="Total de comentarios">{interactions?.comment_count ?? '—'}</span></div> : <button type="button" className="comments-toggle" aria-expanded={commentsOpen} aria-controls={`comments-${post.id}`} onClick={toggleComments}>
        <MessageCircle size={17} aria-hidden="true" /> {commentsOpen ? 'Ocultar comentarios' : 'Ver comentarios'}
      </button>}
      {commentsOpen && <div ref={commentsPanel} id={`comments-${post.id}`} className="comments-panel">
        {commentsLoading ? <p className="comments-state">Cargando comentarios...</p> : <>
          <div ref={commentList} className="comments-list" aria-live="polite">
            {comments.length === 0 && !commentError && <p className={`comments-state${socialDialog ? ' mural-comments-empty' : ''}`}>{socialDialog && <MessageCircle size={20} aria-hidden="true" />}Sé la primera persona en comentar</p>}
            {comments.map(comment=><CommentEntry key={comment.id} comment={comment} userId={user?.id} roleLabel={roleLabels[comment.author_role]||'Lector'} showAvatar={socialDialog} readingEvent={post.feedItemType==='reading_event'} onSave={interactions?.updateComment} onDelete={interactions?.deleteComment} />)}
          </div>
          {(!interactions || interactions.capabilities.can_comment) && <form className="comment-form" onSubmit={submitComment}>
            {socialDialog && <span className="mural-comment-avatar mural-composer-avatar" aria-label={user?.display_name || 'Tu perfil'}>{initialsFor(user?.display_name)}</span>}
            <div className="comment-composer-body">
              <label className={socialDialog ? 'mural-comment-label' : undefined} htmlFor={`comment-${post.id}`}>Escribe un comentario</label>
              <textarea ref={commentInput} id={`comment-${post.id}`} value={commentText} onChange={event => setCommentText(event.target.value)} maxLength={wordLimited ? undefined : COMMENT_LIMIT} rows={socialDialog ? 2 : 3} required placeholder={socialDialog ? 'Escribe tu comentario...' : 'Comparte tu opinión...'} aria-invalid={commentTooLong || undefined} aria-describedby={socialDialog ? `comment-count-${post.id}` : undefined} />
              {commentError && <p className="comment-error" role="alert">{commentError}</p>}
              <div className="comment-composer-bottom">
                {socialDialog && <span id={`comment-count-${post.id}`} className={`comment-character-count${commentTooLong ? ' comment-limit-exceeded' : ''}`}>{wordLimited ? `${commentWords}/200 palabras` : `${commentText.length}/${COMMENT_LIMIT}`}</span>}
                <button type="submit" className={`button primary${socialDialog ? ' mural-comment-send' : ''}`} aria-label={commentSending ? 'Publicando comentario' : 'Publicar comentario'} title="Publicar comentario" aria-busy={commentSending} disabled={commentSending || !commentText.trim() || commentTooLong}>{socialDialog ? <Send size={18} aria-hidden="true" /> : commentSending ? 'Publicando...' : 'Publicar comentario'}</button>
              </div>
            </div>
          </form>}
        </>}
      </div>}
    </section>}
  </article>
}

