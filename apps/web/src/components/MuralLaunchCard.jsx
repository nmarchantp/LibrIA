import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookOpen, Check, Eye, Heart, MessageCircle, Plus, Share2 } from 'lucide-react'
import { apiAssetUrl, apiUrl } from '../api/client'
import { useActivityInteractions } from '../context/ActivityInteractionContext'
import { useLibrary } from '../context/LibraryContext'
import { getGoogleBookById } from '../services/booksService'
import ActivityOptionsMenu from './ActivityOptionsMenu'
import FormattedText from './FormattedText'
import PostGallery from './PostGallery'
import SpoilerShield from './SpoilerShield'
import './MuralLaunchCard.css'

const roleLabels = { lector: 'Lector', influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', editorial: 'Editorial', admin: 'Admin' }
const libraryLabels = { Pendiente: 'En pendientes', Leyendo: 'Leyendo', Terminado: 'Terminado', Abandonado: 'Abandonado' }
const imageUrl = value => /^https?:\/\//i.test(value) ? value : apiUrl(value)
const initialsFor = name => (name || '').split(' ').filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase()

// Mirrors the detail page: some discovery results need an edition chosen on the book page first.
const needsEdition = book => book.catalogFlow === 'discovery-v1' && !book.editionId && !book.selectionReference && !(book.editionOptional && book.workId)

function LaunchCover({ item, bookId }) {
  const [failed, setFailed] = useState(false)
  const src = item.custom_book_cover_url ? apiUrl(item.custom_book_cover_url) : item.book_cover_url ? apiAssetUrl(item.book_cover_url) : null
  const cover = src && !failed ? <img src={src} alt="" onError={() => setFailed(true)} />
    : <span className="bulletin-cover-fallback"><strong>{item.book_title}</strong><BookOpen aria-hidden="true" />{item.book_author && <small>{item.book_author}</small>}</span>
  return bookId ? <Link className="bulletin-cover" to={`/books/${bookId}`} aria-label={`Ver ficha de ${item.book_title}`}>{cover}</Link> : <span className="bulletin-cover">{cover}</span>
}

function WantToRead({ bookId }) {
  const { getBook, addBook } = useLibrary()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const saved = getBook(bookId)
  if (saved) return <span className="bulletin-library-state"><Check aria-hidden="true" />{libraryLabels[saved.status] || 'En tu biblioteca'}</span>
  const add = async () => {
    setBusy(true); setError('')
    try {
      const book = await getGoogleBookById(bookId)
      if (!book) throw new Error('No encontramos este libro en el catálogo.')
      if (needsEdition(book)) { navigate(`/books/${bookId}`); return }
      await addBook(book)
    } catch (cause) { setError(cause.message || 'No se pudo agregar el libro.') }
    finally { setBusy(false) }
  }
  return <>
    <button type="button" className="bulletin-want" disabled={busy} onClick={add}><Plus aria-hidden="true" />{busy ? 'Agregando…' : 'Quiero leer'}</button>
    {error && <p className="bulletin-error" role="alert">{error}</p>}
  </>
}

// Editorial card for the Lanzamientos tab; comments open the shared activity dialog.
export default function MuralLaunchCard({ item, featured = false, onOpen }) {
  const social = useActivityInteractions(item)
  const [shared, setShared] = useState('')
  const bookId = item.book_ref || item.work_id
  const images = (item.images || []).map(imageUrl)
  const title = item.title || item.book_title || 'Publicación de la comunidad'
  const share = async () => {
    const url = new URL(`/?publication=${encodeURIComponent(item.id)}`, location.origin).href
    try {
      if (navigator.share) await navigator.share({ title, url })
      else { await navigator.clipboard.writeText(url); setShared('Enlace copiado') }
    } catch (cause) { if (cause?.name !== 'AbortError') setShared('No se pudo copiar el enlace') }
    setTimeout(() => setShared(''), 2200)
  }
  const body = <>
    <FormattedText className="bulletin-text" text={item.body} />
    {images.length > 0 && <PostGallery images={images} alt={`Imagen de ${title}`} onOpen={() => social.view('open')} editorial />}
  </>

  return <article className={`bulletin-card${featured ? ' is-featured' : ''}`}>
    {item.book_title && <LaunchCover item={item} bookId={bookId} />}
    <div className="bulletin-main">
      <header className="bulletin-author">
        <span className="bulletin-avatar">{item.author_profile_id ? <Link to={`/profiles/${item.author_profile_id}`} aria-label={`Ver perfil de ${item.author}`}>{item.avatar_url ? <img src={apiAssetUrl(item.avatar_url)} alt="" /> : initialsFor(item.author)}</Link> : initialsFor(item.author)}</span>
        <div className="bulletin-person">
          <div><strong>{item.author_profile_id ? <Link to={`/profiles/${item.author_profile_id}`}>{item.author}</Link> : item.author}</strong><span className={`user-role-badge role-${item.author_role}`}>{roleLabels[item.author_role] || 'Lector'}</span></div>
          <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString('es-CL')}</time>
        </div>
        <span className="bulletin-tag">Lanzamiento</span>
        <ActivityOptionsMenu item={item} />
      </header>
      <div className="bulletin-copy">
        {item.title && <h2>{item.title}</h2>}
        {item.is_spoiler ? <SpoilerShield>{body}</SpoilerShield> : body}
        {item.book_title && <div className="bulletin-related">
          <div className="bulletin-related-copy"><small><BookOpen aria-hidden="true" />Obra relacionada</small><strong>{item.book_title}</strong>{item.book_author && <span>· {item.book_author}</span>}</div>
          {bookId && <div className="bulletin-related-actions"><WantToRead bookId={bookId} /><Link className="bulletin-ghost" to={`/books/${bookId}`}>Ver ficha</Link></div>}
        </div>}
      </div>
      <div className="bulletin-actions">
        <button type="button" className="bulletin-like" aria-pressed={social.liked_by_me} aria-busy={social.likeBusy} disabled={social.likeBusy || !social.capabilities.can_like} onClick={() => social.toggleLike()}><Heart fill={social.liked_by_me ? 'currentColor' : 'none'} aria-hidden="true" />Me gusta <span>{social.like_count ?? 0}</span></button>
        <button type="button" disabled={!social.capabilities.can_view} onClick={() => onOpen(item, true)}><MessageCircle aria-hidden="true" />Comentarios <span>{social.comment_count ?? '—'}</span></button>
        <button type="button" aria-label="Compartir publicación" title="Compartir" onClick={share}><Share2 aria-hidden="true" /></button>
        {shared && <span className="bulletin-shared" role="status">{shared}</span>}
        <span className="bulletin-views" aria-label={`${social.view_count ?? '—'} visualizaciones`} title="Visualizaciones únicas de otros usuarios"><Eye aria-hidden="true" />{social.view_count ?? '—'}</span>
      </div>
      {social.error && <p className="bulletin-error" role="alert">{social.error}</p>}
    </div>
  </article>
}
