import { BookOpen, Check, Eye, Heart, MessageCircle, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useState } from 'react'
import { apiAssetUrl } from '../api/client'
import { useActivityInteractions } from '../context/ActivityInteractionContext'
import ActivityOptionsMenu from './ActivityOptionsMenu'

export default function MuralActivityCard({ item, onOpen }) {
  const [failed, setFailed] = useState(false)
  const social = useActivityInteractions(item)
  const initials = item.author.split(' ').slice(0, 2).map(name => name[0]).join('')
  const bookUrl = item.book_ref || item.work_id
  const title = item.book_title || item.title || 'Publicación de la comunidad'
  const isEvent = item.feed_item_type === 'reading_event'
  return <article className={`mural-activity-card${item.reading_event === 'finish' ? ' is-finished' : ''}`}>
    <header className="mural-activity-person"><span className="mural-activity-avatar">{item.avatar_url ? <img src={apiAssetUrl(item.avatar_url)} alt="" loading="lazy" /> : initials}</span><div><strong>{item.author}</strong><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</time></div><ActivityOptionsMenu item={item} /></header>
    <div className="mural-activity-main">
    {(item.book_title || item.book_cover_url) && <Link to={`/books/${bookUrl}`} className="mural-activity-cover" aria-label={`Ver ficha de ${title}`} onClick={event => { if (!bookUrl) { event.preventDefault(); onOpen(item) } }}>
      {item.book_cover_url && !failed ? <img src={apiAssetUrl(item.book_cover_url)} alt="" loading="lazy" onError={() => setFailed(true)} /> : <BookOpen size={27} strokeWidth={1.3} aria-hidden="true" />}
    </Link>}
    {!item.book_title && !item.book_cover_url && <div className="mural-activity-cover" aria-hidden="true"><BookOpen size={27} strokeWidth={1.3} /></div>}
    <div className="mural-activity-copy">
      <h3 title={title}><button className="mural-activity-title" onClick={() => onOpen(item)}>{title}</button></h3>
      {item.book_author && <p className="mural-activity-book-author" title={item.book_author}>{item.book_author}</p>}
      <div className="mural-activity-meta">
      {item.reading_event === 'progress' && <div className="mural-activity-progress"><div className="mural-activity-progress-label"><span>Progreso de lectura</span>{item.progress_percent != null && <strong>{item.progress_percent} %</strong>}</div>{item.progress_percent != null ? <progress max={100} value={item.progress_percent} aria-label={`Progreso de ${item.author}`} /> : <p className="mural-activity-pages">Llegó a la página {item.page}.</p>}</div>}
      {item.reading_event === 'finish' && <span className="mural-finished-badge"><Check size={14} aria-hidden="true" /> Terminado</span>}
      {!isEvent && <>{item.rating != null && <span className="mural-activity-rating"><Star size={13} aria-hidden="true" /> {item.rating}/5</span>}<p className="mural-activity-excerpt">{item.is_spoiler ? 'Contiene spoilers. Abre la reseña para leerla.' : item.body}</p></>}
      </div>
    </div>
    </div>
    <footer className="mural-activity-footer">
      <div className="mural-social-actions">
        <button type="button" className="mural-social-like" aria-label={`${social.liked_by_me ? 'Quitar' : 'Dar'} Me gusta: ${title}`} aria-pressed={social.liked_by_me} aria-busy={social.likeBusy} disabled={social.likeBusy || !social.capabilities.can_like} onClick={event => { event.stopPropagation(); social.toggleLike() }}><Heart size={16} fill={social.liked_by_me ? 'currentColor' : 'none'} aria-hidden="true" /><span>{social.like_count ?? '—'}</span></button>
        <button type="button" className="mural-social-comments" aria-label={`Abrir comentarios: ${title}`} disabled={!social.capabilities.can_view} onClick={event => { event.stopPropagation(); onOpen(item, true) }}><MessageCircle size={16} aria-hidden="true" /><span>{social.comment_count ?? '—'}</span></button>
        {!isEvent && <span className="mural-social-views" aria-label={`${social.view_count ?? '—'} visualizaciones`} title="Visualizaciones únicas de otros usuarios"><Eye size={16} aria-hidden="true" /><span>{social.view_count ?? '—'}</span></span>}
      </div>
      {social.error && <span className="mural-social-error" role="alert">{social.error}</span>}
    </footer>
  </article>
}
