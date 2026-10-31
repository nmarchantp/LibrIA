import { useEffect, useMemo, useRef, useState } from 'react'
import { Bold, BookOpen, CalendarDays, CircleCheck, ImagePlus, Italic, Megaphone, Rocket, Search, SendHorizontal, Smile, Tag, X } from 'lucide-react'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { searchBookCatalog } from '../services/booksService'
import FormattedText from './FormattedText'
import './PostComposer.css'

const roleLabels = { influencer: 'Influencer', autor: 'Autor', libreria: 'Librería', editorial: 'Editorial', admin: 'Admin' }
const composerCopy = {
  influencer: { heading: 'Comparte con tu comunidad', hint: 'Publica anuncios, eventos o lanzamientos para tus lectores.', placeholder: '¿Qué quieres contarle hoy a tu comunidad?' },
  autor: { heading: 'Comparte tu trabajo', hint: 'Publica novedades de tus obras o anuncia un encuentro con lectores.', placeholder: '¿Qué hay de nuevo en tu escritura?' },
  libreria: { heading: 'Publica desde tu librería', hint: 'Comparte promociones, novedades o un evento de tu librería.', placeholder: 'Cuéntale a la comunidad sobre tus libros o actividades.' },
  editorial: { heading: 'Publica desde tu editorial', hint: 'Comparte lanzamientos, promociones y eventos.', placeholder: 'Escribe una novedad editorial.' },
  admin: { heading: 'Publica como administrador', hint: 'Comparte anuncios, eventos o iniciativas con la comunidad lectora.', placeholder: 'Escribe un anuncio, reflexión o aviso para la comunidad…' },
}
// Only publication types the backend stores; each one gets its own label in the mural.
const postTypes = [['news', 'Anuncio', Megaphone], ['event', 'Evento', CalendarDays], ['promotion', 'Promoción', Tag], ['launch', 'Lanzamiento', Rocket]]
const emojis = ['📚', '📖', '✨', '❤️', '🔥', '😍', '😢', '😂', '🤯', '👏', '🎉', '☕', '🌙', '🐉', '🌸', '💬']
const maxLength = 500
const maxImages = 10
const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

function BookLinker({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!open || query.trim().length < 2) { setResults([]); setLoading(false); return }
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setLoading(true); setError('')
      try { setResults((await searchBookCatalog(query, 'title', { signal: controller.signal })).books.slice(0, 6)) }
      catch (cause) { if (cause.name !== 'AbortError') setError('No se pudo buscar en el catálogo.') }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }, 350)
    return () => { clearTimeout(timer); controller.abort() }
  }, [open, query])
  const choose = book => {
    onChange({ ref: String(book.externalId || book.id), title: book.originalTitle || book.title, author: book.author })
    setOpen(false); setQuery('')
  }
  if (!open && value) return <div className="composer-book is-linked">
    <span className="composer-book-icon"><BookOpen aria-hidden="true" /></span>
    <span className="composer-book-copy"><small>Obra enlazada:</small><strong>{value.title}{value.author ? ` · ${value.author}` : ''}</strong></span>
    <button type="button" className="composer-icon-button" aria-label="Quitar obra enlazada" onClick={() => onChange(null)}><X aria-hidden="true" /></button>
    <button type="button" className="composer-pill" onClick={() => setOpen(true)}>Cambiar libro</button>
  </div>
  if (!open) return <button type="button" className="composer-book composer-book-add" onClick={() => setOpen(true)}>
    <span className="composer-book-icon"><BookOpen aria-hidden="true" /></span><span>Enlazar una obra <small>(opcional)</small></span>
  </button>
  return <div className="composer-book is-searching">
    <label className="composer-book-search"><Search aria-hidden="true" /><input autoFocus value={query} onChange={event => setQuery(event.target.value)} placeholder="Busca la obra por título…" aria-label="Buscar la obra a enlazar" /></label>
    <button type="button" className="composer-pill" onClick={() => { setOpen(false); setQuery('') }}>Cancelar</button>
    {(loading || error || results.length > 0 || query.trim().length >= 2) && <div className="composer-book-results" role="status" aria-live="polite">
      {loading ? <p>Buscando…</p> : error ? <p>{error}</p> : results.length ? <ul>{results.map(book => <li key={book.id}><button type="button" onClick={() => choose(book)}><strong>{book.title}</strong><small>{book.author}</small></button></li>)}</ul> : <p>No encontramos obras con ese título.</p>}
    </div>}
  </div>
}

export default function PostComposer({ role, profileId, onCreated }) {
  const { user, retry } = useAuth()
  const copy = composerCopy[role]
  const textRef = useRef(null)
  const [type, setType] = useState('news')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [book, setBook] = useState(null)
  const [images, setImages] = useState([])
  const [dragging, setDragging] = useState(false)
  const [emojiOpen, setEmojiOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [imageError, setImageError] = useState('')
  const previews = useMemo(() => images.map(image => URL.createObjectURL(image)), [images])
  useEffect(() => () => previews.forEach(url => URL.revokeObjectURL(url)), [previews])
  const initials = (user?.display_name || '').trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('').toUpperCase()
  const typeLabel = postTypes.find(([value]) => value === type)[1]

  const addImages = files => {
    const selected = [...images, ...Array.from(files || [])]
    const totalSize = selected.reduce((sum, image) => sum + image.size, 0)
    if (selected.length > maxImages) setImageError(`Puedes adjuntar hasta ${maxImages} imágenes.`)
    else if (selected.some(image => !imageTypes.includes(image.type))) setImageError('Usa imágenes JPEG, PNG, GIF o WebP.')
    else if (selected.some(image => image.size > 5 * 1024 * 1024) || totalSize > 25 * 1024 * 1024) setImageError('Cada imagen puede pesar hasta 5 MB y el total hasta 25 MB.')
    else { setImages(selected); setImageError('') }
  }
  // Inserts text (or wraps the selection) at the caret, keeping the 500-character limit.
  const editBody = (before, after = '') => {
    const element = textRef.current
    const start = element?.selectionStart ?? body.length
    const end = element?.selectionEnd ?? body.length
    const next = body.slice(0, start) + before + body.slice(start, end) + after + body.slice(end)
    if (next.length > maxLength) return
    setBody(next)
    requestAnimationFrame(() => { element?.focus(); element?.setSelectionRange(start + before.length, end + before.length) })
  }
  const submit = async event => {
    event.preventDefault()
    setBusy(true); setError('')
    try {
      const form = new FormData()
      const publication = { source: type === 'event' ? 'event' : 'community', publication_type: type, kind: 'community',
        author_profile_id: profileId, title: title.trim(), body: body.trim(), book_ref: book?.ref || '', book_title: book?.title || '' }
      Object.entries(publication).forEach(([key, value]) => form.append(key, value))
      images.forEach(image => form.append('images', image))
      await apiRequest('/posts', { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, body: form })
      setTitle(''); setBody(''); setBook(null); setImages([])
      onCreated()
    } catch (cause) {
      if (cause.status === 403) retry()
      setError(cause.status === 403 ? 'Tu perfil ya no tiene permiso para este tipo de publicación.'
        : cause.status === 422 && book && cause.message?.toLowerCase().includes('obra') ? 'Esa obra no está disponible en el catálogo de LibrIA. Prueba con otra o publica sin enlazarla.'
          : 'No se pudo publicar. Inténtalo de nuevo.')
    } finally { setBusy(false) }
  }

  return <form className="post-composer composer" onSubmit={submit} aria-busy={busy}>
    <header className="composer-header">
      <span className="composer-avatar" aria-hidden="true">{initials}</span>
      <div><h2>{copy.heading}{roleLabels[role] && <span className="composer-role">{roleLabels[role]}</span>}</h2><p>{copy.hint}</p></div>
    </header>

    <div className="composer-field">
      <span className="composer-label" id="composer-type-label">Tipo de publicación</span>
      <div className="composer-types" role="group" aria-labelledby="composer-type-label">
        {postTypes.map(([value, label, Icon]) => <button type="button" key={value} className={type === value ? 'active' : ''} aria-pressed={type === value} onClick={() => setType(value)}><Icon aria-hidden="true" />{label}</button>)}
      </div>
    </div>

    <input className="composer-title" value={title} onChange={event => setTitle(event.target.value)} maxLength="200" placeholder="Título opcional (ej: Lectura conjunta de noviembre)" aria-label="Título opcional" />

    <div className="composer-editor">
      <textarea ref={textRef} value={body} onChange={event => setBody(event.target.value)} maxLength={maxLength} rows="4" required placeholder={copy.placeholder} aria-label="Texto de la publicación"
        onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && ['b', 'i'].includes(event.key.toLowerCase())) { event.preventDefault(); editBody(event.key.toLowerCase() === 'b' ? '**' : '*', event.key.toLowerCase() === 'b' ? '**' : '*') } }} />
      <div className="composer-toolbar">
        <button type="button" className="composer-icon-button" title="Negrita (Ctrl+B)" aria-label="Negrita" onClick={() => editBody('**', '**')}><Bold aria-hidden="true" /></button>
        <button type="button" className="composer-icon-button" title="Cursiva (Ctrl+I)" aria-label="Cursiva" onClick={() => editBody('*', '*')}><Italic aria-hidden="true" /></button>
        <span className="composer-toolbar-divider" aria-hidden="true" />
        <div className="composer-emoji">
          <button type="button" className="composer-icon-button" aria-label="Insertar emoji" aria-expanded={emojiOpen} onClick={() => setEmojiOpen(open => !open)}><Smile aria-hidden="true" /></button>
          {emojiOpen && <div className="composer-emoji-panel" role="group" aria-label="Emojis" onKeyDown={event => { if (event.key === 'Escape') setEmojiOpen(false) }}>
            {emojis.map(emoji => <button type="button" key={emoji} onClick={() => { editBody(emoji); setEmojiOpen(false) }}>{emoji}</button>)}
          </div>}
        </div>
        <span className="composer-counter" aria-live="polite">{body.length}/{maxLength}
          <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" /><circle cx="10" cy="10" r="8" className="composer-counter-fill" style={{ strokeDashoffset: 50.27 * (1 - body.length / maxLength) }} /></svg>
        </span>
      </div>
    </div>
    {body.includes('*') && <div className="composer-preview"><span>Así se verá:</span><FormattedText text={body} className="post-text" /></div>}

    <BookLinker value={book} onChange={setBook} />

    <div className="composer-field">
      <div className="composer-images-heading"><span className="composer-label">Imágenes de apoyo ({images.length}/{maxImages})</span><small>JPEG, PNG, GIF o WebP hasta 5 MB</small></div>
      <label className={`composer-dropzone${dragging ? ' is-dragging' : ''}`}
        onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)}
        onDrop={event => { event.preventDefault(); setDragging(false); addImages(event.dataTransfer.files) }}>
        <input type="file" className="composer-file-input" accept={imageTypes.join(',')} multiple onChange={event => { addImages(event.target.files); event.target.value = '' }} disabled={images.length >= maxImages} />
        <span className="composer-dropzone-icon"><ImagePlus aria-hidden="true" /></span>
        <strong>Haz clic o arrastra fotos aquí</strong>
        <small>Puedes sumar portadas, fotos de tu lectura o afiches.</small>
      </label>
      {images.length > 0 && <ul className="composer-thumbs">{images.map((image, index) => <li key={`${image.name}-${index}`}>
        <img src={previews[index]} alt="" />
        <button type="button" aria-label={`Quitar ${image.name}`} onClick={() => { setImages(current => current.filter((_, itemIndex) => itemIndex !== index)); setImageError('') }}><X aria-hidden="true" /></button>
      </li>)}</ul>}
      {imageError && <p className="comment-error" role="alert">{imageError}</p>}
    </div>

    {error && <p className="comment-error" role="alert">{error}</p>}
    <footer className="composer-footer">
      <span><CircleCheck aria-hidden="true" />Visible para todos los miembros de LibrIA</span>
      <button className="button primary" disabled={busy || !body.trim() || Boolean(imageError)}><SendHorizontal aria-hidden="true" />{busy ? 'Publicando…' : `Publicar ${typeLabel.toLowerCase()}`}</button>
    </footer>
  </form>
}
