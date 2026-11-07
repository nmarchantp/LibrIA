import GenreSelector from './GenreSelector'
import ProfileEditModal from './ProfileEditModal'
import { useEffect, useState } from 'react'
import { BookOpen, LibraryBig, Pencil, Sprout } from 'lucide-react'
import PreferenceTags from './PreferenceTags'
import { profileService } from '../services/profileService'

const storyImages = { flowers: '/images/story-books-candles.png', books: '/images/story-books-coffee.png', cat: '/images/story-books-cat-candle-left.png' }
const storyOptions = [['flowers', 'Con flores'], ['books', 'Libros y caf\u00e9'], ['cat', 'Libros y gato'], ['none', 'Sin imagen']]

export default function ProfileAboutCard({ biography, storyIllustration = 'flowers', genres = [], editable = false, onSave, section = 'biography' }) {
  const isBiography = section === 'biography'
  const title = isBiography ? 'Mi historia' : 'Mis géneros favoritos'
  const [editing, setEditing] = useState(false)
  const [illustration, setIllustration] = useState(storyIllustration)
  const [draft, setDraft] = useState('')
  const [initial, setInitial] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [genreIds, setGenreIds] = useState([])
  const [options, setOptions] = useState(null)
  const [catalogError, setCatalogError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const length = Array.from(draft).length
  useEffect(() => {
    if (!editing || isBiography) return
    let active = true
    setOptions(null); setCatalogError('')
    profileService.catalogs().then(data => { if (active) setOptions(data.genres) })
      .catch(() => { if (active) setCatalogError('No se pudieron cargar los géneros.') })
    return () => { active = false }
  }, [editing, attempt, isBiography])
  function edit() {
    setIllustration(storyIllustration); setDraft(biography || ''); setGenreIds(genres.map(genre => genre.id))
    setInitial(JSON.stringify(isBiography ? [biography || '', storyIllustration] : genres.map(genre => genre.id)))
    setError(''); setEditing(true)
  }
  function toggleGenre(id) {
    setGenreIds(current => current.includes(id) ? current.filter(value => value !== id) : current.length < 5 ? [...current, id] : current)
  }
  const availableGenres = [...(options || []), ...genres.filter(genre => !options?.some(option => option.id === genre.id))]
  async function save(event) {
    event.preventDefault()
    if (busy || (isBiography ? length > 70 && draft !== (biography || '') : genreIds.length > 5 || !options)) return
    setBusy(true); setError('')
    try { await onSave(isBiography ? { ...(draft !== (biography || '') ? { biography: draft } : {}), story_illustration: illustration } : { genre_ids: genreIds }); setEditing(false); setMessage('Sobre mí guardado.') }
    catch (cause) { setError(cause.message || 'No se pudo guardar Sobre mí.') }
    finally { setBusy(false) }
  }
  return <section className={`reader-personal-card reader-about ${isBiography ? `reader-story reader-story-${storyIllustration}${storyIllustration === 'none' ? ' reader-story-no-image' : ''}` : 'reader-favorite-genres'}`}>
    <div className="reader-card-heading"><h2>{isBiography ? <BookOpen size={23} aria-hidden="true" /> : <LibraryBig size={23} aria-hidden="true" />}{title}</h2>{editable && <button className="reader-edit-button" type="button" aria-label={`Editar ${title}`} onClick={edit}><Pencil size={15} aria-hidden="true" /></button>}</div>
    {!isBiography && <p className="reader-card-description">Los géneros que más disfruto leer.</p>}
    {(isBiography ? (storyImages[storyIllustration] && <img className="reader-story-decoration-slot" src={storyImages[storyIllustration]} alt="" aria-hidden="true" />) : <span className="reader-card-decoration" data-decoration-slot="genre-books-flowers" aria-hidden="true"><LibraryBig /><Sprout /></span>)}
    {isBiography ? <p className={biography ? 'reader-biography' : 'reader-module-empty'}>{biography || 'Aún no hay una biografía. Este espacio está reservado para una historia lectora.'}</p> : <PreferenceTags values={genres} empty="Aún no has elegido géneros que te representen." />}
    <ProfileEditModal open={editable && editing} title={`Editar ${title}`} icon={isBiography ? <BookOpen /> : <LibraryBig />} description={isBiography ? 'Cuenta tu historia lectora en un máximo de 70 caracteres.' : 'Elige hasta cinco géneros que te representen.'}
      dirty={initial !== JSON.stringify(isBiography ? [draft, illustration] : genreIds)} busy={busy} saveDisabled={isBiography ? length > 70 && draft !== (biography || '') : genreIds.length > 5 || !options} onSubmit={save} onClose={() => { setEditing(false); setError('') }}>
      {isBiography && <><label htmlFor="profile-biography">Tu biografía</label>
      <textarea id="profile-biography" value={draft} rows={5} disabled={busy} onChange={event => setDraft(event.target.value)} aria-describedby="biography-count biography-visibility" />
      <span id="biography-count" className={length > 70 ? 'reader-field-error' : 'reader-field-count'} aria-live="polite">{length}/70 caracteres</span><fieldset className="reader-story-image-options" disabled={busy}><legend>Ilustración de tu historia</legend><div>{storyOptions.map(([value, label]) => <label key={value}><input type="radio" name="story-illustration" value={value} checked={illustration === value} onChange={() => setIllustration(value)} />{storyImages[value] ? <img src={storyImages[value]} alt="" /> : <span className="reader-story-no-image-preview" aria-hidden="true"><BookOpen /></span>}<span>{label}</span></label>)}</div></fieldset></>}
      {!isBiography && !options && !catalogError && <p role="status">Cargando géneros…</p>}
      {!isBiography && catalogError && <div><p className="reader-field-error" role="alert">{catalogError}</p><button className="reader-edit-button" type="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></div>}
      {!isBiography && options && <GenreSelector options={availableGenres} selected={genreIds} onToggle={toggleGenre} disabled={busy} />}
      <p id={isBiography ? 'biography-visibility' : undefined}>Visible para toda la comunidad de LibrIAverse.</p>
      {error && <p className="reader-field-error" role="alert">{error}</p>}
    </ProfileEditModal>
    {message && <p className="reader-save-status" role="status">{message}</p>}
  </section>
}
