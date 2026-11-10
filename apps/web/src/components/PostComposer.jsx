import { useEffect, useMemo, useRef, useState } from 'react'
import { Bold, BookOpen, CalendarDays, Camera, CircleCheck, ImagePlus, Italic, Megaphone, Rocket, Search, SendHorizontal, Smile, Tag, X } from 'lucide-react'
import { apiRequest, apiUrl } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { searchBookCatalog } from '../services/booksService'
import FormattedText from './FormattedText'
import PublicationCoverPicker from './PublicationCoverPicker'
import EventFields from './EventFields'
import './EventPresentation.css'
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
    onChange({ ref: String(book.externalId || book.id), title: book.originalTitle || book.title, author: book.author, cover: book.image })
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

export default function PostComposer({ role, profileId, onCreated, initialPost = null, onBusyChange, onDirtyChange, onCancel, initialType = 'news' }) {
  const { retry } = useAuth()
  const copy = initialPost ? { heading:'Editar publicación',hint:'Actualiza el contenido conservando sus comentarios e interacciones.',placeholder:'Texto de la publicación' } : composerCopy[role]
  const textLimit = initialPost ? 3000 : maxLength
  const textRef = useRef(null)
  const publishing = useRef(false)
  const [type, setType] = useState(initialPost?.publication_type || (initialPost?.source==='event'?'event':initialType))
  const [title, setTitle] = useState(initialPost?.title || '')
  const [body, setBody] = useState(initialPost?.body || '')
  const [book, setBook] = useState(initialPost?.book_title ? {ref:initialPost.book_ref||String(initialPost.work_id||''),title:initialPost.book_title,author:initialPost.book_author,cover:initialPost.book_cover_url,work_id:initialPost.work_id,edition_id:initialPost.edition_id} : null)
  const [coverMode,setCoverMode] = useState(initialPost?.custom_book_cover_url?'custom':'catalog')
  const [coverFile,setCoverFile] = useState(null)
  const [images, setImages] = useState([])
  const [existingImages,setExistingImages] = useState(initialPost?.images||[])
  const [eventValues,setEventValues]=useState(()=>({start_date:initialPost?.event_details?.start_date||'',start_time:initialPost?.event_details?.start_time||'',end_date:initialPost?.event_details?.end_date||'',end_time:initialPost?.event_details?.end_time||'',timezone:initialPost?.event_details?.timezone||'America/Santiago',location:initialPost?.event_details?.location||'',organizer:initialPost?.event_details?.organizer||'',category:initialPost?.event_details?.category||'meetup'}))
  const snapshot=JSON.stringify({type,title,body,book,coverMode,eventValues,existingImages,images:images.map(image=>[image.name,image.size,image.lastModified]),coverFile:coverFile&&[coverFile.name,coverFile.size,coverFile.lastModified]})
  const baseline=useRef(snapshot)
  useEffect(()=>onDirtyChange?.(snapshot!==baseline.current),[snapshot,onDirtyChange])
  const eventRequired=type==='event'&&(!initialPost||initialPost.publication_type!=='event'||Boolean(initialPost.event_details)||Boolean(eventValues.start_date||eventValues.start_time))
  const [dragging, setDragging] = useState(false)
  const [emojiOpen, setEmojiOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  useEffect(()=>onBusyChange?.(busy),[busy,onBusyChange])
  const [error, setError] = useState('')
  const [imageError, setImageError] = useState('')
  const previews = useMemo(() => images.map(image => URL.createObjectURL(image)), [images])
  useEffect(() => () => previews.forEach(url => URL.revokeObjectURL(url)), [previews])
  const selectableTypes = initialPost && !postTypes.some(([value])=>value===initialPost.publication_type) ? [[initialPost.publication_type,({note:'Nota',theory:'Teoría',free:'Publicación',institutional:'Institucional'})[initialPost.publication_type]||'Publicación',BookOpen],...postTypes] : postTypes
  const typeLabel = selectableTypes.find(([value]) => value === type)?.[1] || 'Publicación'

  const addImages = files => {
    const selected = [...images, ...Array.from(files || [])]
    const totalSize = selected.reduce((sum, image) => sum + image.size, 0)
    if (selected.length + existingImages.length > maxImages) setImageError(`Puedes adjuntar hasta ${maxImages} imágenes.`)
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
    if (next.length > textLimit) return
    setBody(next)
    requestAnimationFrame(() => { element?.focus(); element?.setSelectionRange(start + before.length, end + before.length) })
  }
  const submit = async event => {
    event.preventDefault()
    if(publishing.current)return
    publishing.current=true
    setBusy(true); setError('')
    try {
      const form = new FormData()
      const publication = { source: type === 'event' ? 'event' : 'community', publication_type: type, kind: 'community',
        author_profile_id: profileId, title: title.trim(), body: body.trim(), book_ref: book?.ref || '', book_title: book?.title || '' }
      if(initialPost) {
        publication.work_id=book?.work_id||'';publication.edition_id=book?.edition_id||''
        publication.existing_image_ids=JSON.stringify(existingImages.map(path=>path.split('/').at(-1)))
        publication.cover_mode=coverMode==='catalog'?'catalog':coverFile?'custom':'keep'
      }
      if(type==='event'&&eventValues.start_date)publication.event_details=JSON.stringify({...eventValues,end_date:eventValues.end_date||null,end_time:eventValues.end_time||null})
      Object.entries(publication).forEach(([key, value]) => form.append(key, value))
      images.forEach(image => form.append('images', image))
      if(book&&coverMode==='custom'&&coverFile)form.append('book_cover',coverFile)
      const saved=await apiRequest(initialPost?`/posts/${initialPost.id}`:'/posts', { method: initialPost?'PUT':'POST', headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}`, ...(initialPost?.moderation_version ? { 'If-Match': String(initialPost.moderation_version) } : {}) }, body: form })
      setTitle(''); setBody(''); setBook(null); setImages([])
      setEventValues({start_date:'',start_time:'',end_date:'',end_time:'',timezone:'America/Santiago',location:'',organizer:'',category:'meetup'})
      setCoverMode('catalog');setCoverFile(null)
      if(type==='event'||initialPost?.source==='event')window.dispatchEvent(new Event('libria-events-updated'))
      onCreated(saved)
    } catch (cause) {
      if (cause.status === 403) retry()
      setError(cause.status === 403 ? 'Tu perfil ya no tiene permiso para este tipo de publicación.'
        : cause.status === 422 && book && cause.message?.toLowerCase().includes('obra') ? 'Esa obra no está disponible en el catálogo de LibrIA. Prueba con otra o publica sin enlazarla.'
          : [413,415,422].includes(cause.status) ? cause.message : 'No se pudo publicar. Inténtalo de nuevo.')
    } finally { publishing.current=false;setBusy(false) }
  }

  return <form className="post-composer composer" onSubmit={submit} aria-busy={busy}>
    <div className="composer-field">
      <span className="composer-label" id="composer-type-label">Tipo de publicación</span>
      <div className="composer-types" role="group" aria-labelledby="composer-type-label">
        {selectableTypes.map(([value, label, Icon]) => <button type="button" key={value} className={type === value ? 'active' : ''} aria-pressed={type === value} onClick={() => setType(value)}><Icon aria-hidden="true" />{label}</button>)}
      </div>
    </div>

    <input className="composer-title" value={title} onChange={event => setTitle(event.target.value)} maxLength="200" required={type==='event'} placeholder={type==='event'?'Título del evento':'Título opcional (ej: Lectura conjunta de noviembre)'} aria-label={type==='event'?'Título del evento':'Título opcional'} />

    <div className="composer-editor">
      <textarea ref={textRef} value={body} onChange={event => setBody(event.target.value)} maxLength={textLimit} rows="4" required placeholder={copy.placeholder} aria-label="Texto de la publicación"
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
        <span className="composer-counter" aria-live="polite">{body.length}/{textLimit}
          <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" /><circle cx="10" cy="10" r="8" className="composer-counter-fill" style={{ strokeDashoffset: 50.27 * (1 - body.length / textLimit) }} /></svg>
        </span>
      </div>
    </div>
    {body.includes('*') && <div className="composer-preview"><span>Así se verá:</span><FormattedText text={body} className="post-text" /></div>}

    <div className="composer-attachments"><div className="composer-related-column">
    <BookLinker value={book} onChange={value=>{setBook(value);setCoverFile(null);setCoverMode('catalog')}} />
    <PublicationCoverPicker mode={coverMode} onModeChange={setCoverMode} file={coverFile} onChange={setCoverFile} currentUrl={initialPost?.custom_book_cover_url?apiUrl(initialPost.custom_book_cover_url):null} catalogUrl={book?.cover} disabled={busy||!book} />
    {!book&&<p className="composer-cover-hint">Selecciona una obra para usar su portada o subir una imagen propia.</p>}

    </div><div className="composer-field composer-photo-column">
      <div className="composer-images-heading"><span className="composer-label">Imágenes de apoyo ({images.length+existingImages.length}/{maxImages})</span><small>JPEG, PNG, GIF o WebP hasta 5 MB</small></div>
      <label className={`composer-dropzone${dragging ? ' is-dragging' : ''}`}
        onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)}
        onDrop={event => { event.preventDefault(); setDragging(false); addImages(event.dataTransfer.files) }}>
        <input type="file" className="composer-file-input" accept={imageTypes.join(',')} multiple onChange={event => { addImages(event.target.files); event.target.value = '' }} disabled={images.length+existingImages.length >= maxImages} />
        <span className="composer-dropzone-icon"><ImagePlus aria-hidden="true" /></span>
        <strong>Agregar fotografías</strong>
        <small>También puedes arrastrarlas aquí.</small>
      </label>
      <label className="composer-camera"><Camera size={16} aria-hidden="true" />Tomar foto<input type="file" className="composer-file-input" accept="image/*" capture="environment" disabled={busy||images.length+existingImages.length>=maxImages} onChange={event=>{addImages(event.target.files);event.target.value=''}} /></label>
      {existingImages.length>0&&<ul className="composer-thumbs">{existingImages.map(path=><li key={path}><img src={/^https?:/.test(path)?path:apiUrl(path)} alt="Imagen adjunta actual" /><button type="button" aria-label="Quitar imagen adjunta" onClick={()=>setExistingImages(current=>current.filter(value=>value!==path))}><X /></button></li>)}</ul>}
      {images.length > 0 && <ul className="composer-thumbs">{images.map((image, index) => <li key={`${image.name}-${index}`}>
        <img src={previews[index]} alt="" />
        <button type="button" aria-label={`Quitar ${image.name}`} onClick={() => { setImages(current => current.filter((_, itemIndex) => itemIndex !== index)); setImageError('') }}><X aria-hidden="true" /></button>
      </li>)}</ul>}
      {imageError && <p className="comment-error" role="alert">{imageError}</p>}
    </div>

    </div>
    {type==='event'&&<EventFields value={eventValues} onChange={setEventValues} required={eventRequired} disabled={busy} />}
    {error && <p className="comment-error" role="alert">{error}</p>}
    <footer className="composer-footer">
      <span><CircleCheck aria-hidden="true" />Visible para todos los miembros de LibrIA</span>
      {onCancel&&<button type="button" className="button" disabled={busy} onClick={onCancel}>Cancelar</button>}
      <button className="button primary" disabled={busy || !body.trim() || Boolean(imageError) || (book&&coverMode==='custom'&&!coverFile&&!initialPost?.custom_book_cover_url)}><SendHorizontal aria-hidden="true" />{busy ? 'Guardando…' : initialPost?'Guardar cambios':`Publicar ${typeLabel.toLowerCase()}`}</button>
    </footer>
  </form>
}
