import { useEffect, useId, useState } from 'react'
import { BookOpen, Heart, Pencil, Search, UserRound, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import ProfileEditModal from './ProfileEditModal'
import { searchBookCatalog } from '../services/booksService'
import { apiRequest } from '../api/client'
import './ProfileLiteraryHighlights.css'

const emptyCrush = { name: '', book: '', description: '', image_url: '', work_id: null, character_id: null }

function CrushOrnament({ bottom = false }) {
  return <svg className={`literary-crush-ornament${bottom ? ' is-bottom' : ''}`} viewBox="0 0 160 130" fill="none" aria-hidden="true"><path d="M12 12C78 7 55 73 118 69S130 111 150 123M58 38C80 21 108 22 127 10M97 65C80 80 88 100 105 107" /><path d="M27 13Q22 0 10 5Q12 18 27 13ZM41 22Q28 19 26 34Q40 36 41 22ZM59 41Q64 26 77 29Q77 44 59 41ZM75 55Q59 49 57 64Q68 71 75 55ZM99 67Q98 51 111 49Q118 62 99 67ZM124 77Q139 66 145 80Q137 91 124 77ZM133 95Q119 93 120 107Q132 111 133 95ZM89 75Q73 69 72 83Q85 88 89 75ZM95 94Q106 83 113 95Q107 105 95 94Z" /><path className="literary-crush-moon" d="M143 10A20 20 0 1 0 152 44A18 18 0 0 1 143 10Z" /></svg>
}

function Artwork({ src, title, portrait = false }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [src])
  return src && !failed ? <img src={src} alt={title} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} /> : <span className="literary-highlight-placeholder" aria-label={title}>{portrait ? <UserRound /> : <BookOpen />}<span>{portrait ? '' : title}</span></span>
}

export default function ProfileLiteraryHighlights({ crush, books = [], editable, onSave }) {
  const [editing, setEditing] = useState(null)
  const [draft, setDraft] = useState(emptyCrush)
  const [selected, setSelected] = useState([])
  const [initial, setInitial] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [characters, setCharacters] = useState([])
  const [characterLoading, setCharacterLoading] = useState(false)
  const [characterError, setCharacterError] = useState('')
  const [characterAttempt, setCharacterAttempt] = useState(0)
  const id = useId()
  useEffect(() => {
    if (!editing || query.trim().length < 2) { setResults([]); setSearching(false); return }
    const controller = new AbortController()
    setSearching(true); setSearchError(''); setResults([])
    const timer = setTimeout(() => {
      searchBookCatalog(query, 'all', { signal: controller.signal, localOnly: editing === 'crush' }).then(data => {
        if (!controller.signal.aborted) setResults(data.books)
      }).catch(() => { if (!controller.signal.aborted) setSearchError('No se pudo buscar. Cambia la búsqueda para intentarlo de nuevo.') })
        .finally(() => { if (!controller.signal.aborted) setSearching(false) })
    }, 300)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query, editing])
  useEffect(() => {
    setCharacters([]); setCharacterError('')
    if (editing !== 'crush' || !draft.work_id) { setCharacterLoading(false); return }
    const controller = new AbortController()
    setCharacterLoading(true)
    apiRequest(`/books/${encodeURIComponent(draft.work_id)}/characters`, { headers: { Authorization: `Bearer ${localStorage.getItem('libria_token')}` }, signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setCharacters(data.items || []) })
      .catch(() => { if (!controller.signal.aborted) setCharacterError('No se pudieron cargar los personajes de este libro.') })
      .finally(() => { if (!controller.signal.aborted) setCharacterLoading(false) })
    return () => controller.abort()
  }, [editing, draft.work_id, characterAttempt])
  function open(kind) {
    const value = kind === 'crush' ? { ...emptyCrush, ...crush, image_url: crush?.image_url || '' } : books
    setDraft(kind === 'crush' ? value : emptyCrush); setSelected(kind === 'books' ? value : [])
    setInitial(JSON.stringify(value)); setQuery(''); setError(''); setSearchError(''); setEditing(kind)
  }
  async function save(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try {
      await onSave(editing === 'crush' ? { literary_crush: draft.character_id ? { character_id: draft.character_id, work_id: draft.work_id, description: draft.description } : null } : { essential_books: selected })
      setEditing(null); setMessage('Tus favoritos se guardaron.')
    } catch (cause) { setError(cause.message || 'No se pudieron guardar tus favoritos.') }
    finally { setBusy(false) }
  }
  const pencil = (kind, title) => editable && <button className="reader-edit-button" type="button" aria-label={`Editar ${title}`} onClick={() => open(kind)}><Pencil size={14} /></button>
  return <>
    <section className="reader-personal-card reader-literary-crush">
      <CrushOrnament /><CrushOrnament bottom />
      <div className="reader-card-heading"><h2><Heart size={20} />Mi crush literario</h2>{pencil('crush', 'Mi crush literario')}</div>
      {crush ? <div className="literary-crush-content"><div className="literary-crush-portrait"><Artwork src={crush.image_url} title={crush.name} portrait /></div><div className="literary-crush-details"><h3>{crush.name}</h3>{crush.book && <p className="literary-crush-book">{crush.book}</p>}{crush.description && <><span className="literary-crush-divider" aria-hidden="true">✦</span><p className="literary-crush-description">{crush.description}</p></>}</div></div> : <p className="reader-module-empty">Ese personaje que se quedó contigo. Añade tu crush literario.</p>}
    </section>
    <section className="reader-personal-card reader-essential-books">
      <div className="reader-card-heading"><h2><BookOpen size={20} />Mis libros imprescindibles</h2>{pencil('books', 'Mis libros imprescindibles')}</div>
      {books.length ? <div className="literary-essential-shelf">{books.map(book => <Link key={book.id} to={`/books/${encodeURIComponent(book.id)}`} title={book.title}><Artwork src={book.image_url} title={book.title} /></Link>)}</div> : <p className="reader-module-empty">Elige hasta cuatro libros que siempre recomendarías.</p>}
    </section>
    <ProfileEditModal open={Boolean(editing) && editable} title={editing === 'crush' ? 'Mi crush literario' : 'Mis libros imprescindibles'} icon={editing === 'crush' ? <Heart /> : <BookOpen />} description={editing === 'crush' ? 'Busca un libro de LibrIA y elige tu personaje entre sus retratos disponibles.' : 'Busca y elige hasta cuatro libros, en el orden que quieras mostrarlos.'} dirty={initial !== JSON.stringify(editing === 'crush' ? draft : selected)} busy={busy} saveDisabled={editing === 'crush' && Boolean(draft.work_id || draft.name) && (!draft.character_id || characterLoading || Boolean(characterError) || !characters.some(item => item.id === draft.character_id))} onClose={() => setEditing(null)} onSubmit={save}>
      {editing === 'crush' ? <div className="literary-highlight-fields">
        <label htmlFor={`${id}-crush-book`}>Libro o saga<input id={`${id}-crush-book`} type="search" value={query} disabled={busy} placeholder="Busca en el catálogo de LibrIA" onChange={event => setQuery(event.target.value)} /></label>
        {searching && <p role="status">Buscando en LibrIA…</p>}{searchError && <p role="alert">{searchError}</p>}
        {!searching && !searchError && query.trim().length >= 2 && !results.length && <p>No hay libros de LibrIA para esta búsqueda.</p>}
        {results.length > 0 && <ul className="literary-highlight-results literary-crush-book-results">{results.map(book => <li key={book.id}><button type="button" disabled={busy} onClick={() => { setDraft(current => ({ ...emptyCrush, description: current.description, work_id: book.id, book: book.title })); setQuery(''); setResults([]) }}><Artwork src={book.image} title={book.title} /><span>{book.title}<small>{book.author}</small></span></button></li>)}</ul>}
        {draft.book && <div className="literary-crush-selected-book"><BookOpen size={17} /><strong>{draft.book}</strong><button type="button" disabled={busy} onClick={() => setDraft({ ...emptyCrush })}>Quitar selección</button></div>}
        {characterLoading && <p role="status">Cargando personajes…</p>}
        {characterError && <div><p role="alert">{characterError}</p><button type="button" onClick={() => setCharacterAttempt(value => value + 1)}>Reintentar</button></div>}
        {draft.work_id && !characterLoading && !characterError && (characters.length ? <fieldset className="literary-character-picker" disabled={busy}><legend>Elige tu personaje</legend><div>{characters.map(character => <label key={character.id}><input type="radio" name={`${id}-character`} checked={draft.character_id === character.id} onChange={() => setDraft(current => ({ ...current, character_id: character.id, name: character.name, image_url: character.image_url || '' }))} /><Artwork src={character.image_url} title={character.name} portrait /><span>{character.name}</span></label>)}</div></fieldset> : <p>Aún no hay personajes con retrato registrados para este libro.</p>)}
        {!draft.work_id && draft.name && <p>Vuelve a elegir el libro y el personaje para vincular tu selección anterior al catálogo.</p>}
        <label htmlFor={`${id}-description`}>Qué te gusta de este personaje<textarea id={`${id}-description`} value={draft.description} maxLength={300} disabled={busy} onChange={event => setDraft(current => ({ ...current, description: event.target.value }))} /></label>
      </div> : <>
        <ul className="literary-highlight-selected">{selected.map(book => <li key={book.id}><span>{book.title}</span><button type="button" aria-label={`Quitar ${book.title}`} disabled={busy} onClick={() => setSelected(current => current.filter(item => item.id !== book.id))}><X size={16} /></button></li>)}</ul>
        <label htmlFor={`${id}-search`}><Search size={16} />Buscar libros ({selected.length}/4)</label><input id={`${id}-search`} type="search" value={query} disabled={busy} onChange={event => setQuery(event.target.value)} placeholder="Título o autor" />
        {searching && <p role="status">Buscando libros…</p>}{searchError && <p role="alert">{searchError}</p>}
        {!searching && !searchError && query.trim().length >= 2 && !results.length && <p>No encontramos libros para esa búsqueda.</p>}
        <ul className="literary-highlight-results">{results.map(book => <li key={book.id}><button type="button" disabled={busy || selected.length >= 4 || selected.some(item => item.id === book.id)} onClick={() => setSelected(current => current.length >= 4 || current.some(item => item.id === book.id) ? current : [...current, { id: book.id, title: book.title, image_url: book.image || null }])}><Artwork src={book.image} title={book.title} /><span>{book.title}<small>{book.author}</small></span></button></li>)}</ul>
      </>}
      <p>Se comparte con la misma privacidad que «Mi historia».</p>
      {error && <p role="alert" className="reader-field-error">{error}</p>}
    </ProfileEditModal>
    {message && <p className="reader-save-status literary-highlight-status" role="status">{message}</p>}
  </>
}
