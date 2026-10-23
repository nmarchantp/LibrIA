import GenreSelector from './GenreSelector'
import ProfileEditModal from './ProfileEditModal'
import { useEffect, useState } from 'react'
import { BookOpen, LibraryBig, Pencil, Sprout } from 'lucide-react'
import PreferenceTags from './PreferenceTags'
import { profileService } from '../services/profileService'

export default function ProfileAboutCard({ biography, genres = [], editable = false, onSave, section = 'biography' }) {
  const isBiography = section === 'biography'
  const title = isBiography ? 'Mi historia' : 'Mis géneros favoritos'
  const [editing, setEditing] = useState(false)
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
    setDraft(biography || ''); setGenreIds(genres.map(genre => genre.id))
    setInitial(JSON.stringify(isBiography ? biography || '' : genres.map(genre => genre.id)))
    setError(''); setEditing(true)
  }
  function toggleGenre(id) {
    setGenreIds(current => current.includes(id) ? current.filter(value => value !== id) : current.length < 5 ? [...current, id] : current)
  }
  const availableGenres = [...(options || []), ...genres.filter(genre => !options?.some(option => option.id === genre.id))]
  async function save(event) {
    event.preventDefault()
    if (busy || (isBiography ? length > 200 : genreIds.length > 5 || !options)) return
    setBusy(true); setError('')
    try { await onSave(isBiography ? { biography: draft } : { genre_ids: genreIds }); setEditing(false); setMessage('Sobre mí guardado.') }
    catch (cause) { setError(cause.message || 'No se pudo guardar Sobre mí.') }
    finally { setBusy(false) }
  }
  return <section className={`reader-personal-card reader-about ${isBiography ? 'reader-story' : 'reader-favorite-genres'}`}>
    <div className="reader-card-heading"><h2>{isBiography ? <BookOpen size={23} aria-hidden="true" /> : <LibraryBig size={23} aria-hidden="true" />}{title}</h2>{editable && <button className="reader-edit-button" type="button" aria-label={`Editar ${title}`} onClick={edit}><Pencil size={15} aria-hidden="true" /><span>Editar</span></button>}</div>
    {!isBiography && <p className="reader-card-description">Los géneros que más disfruto leer.</p>}
    {(isBiography ? <span className="reader-story-decoration-slot" data-decoration-slot="story-books-candles" aria-hidden="true" /> : <span className="reader-card-decoration" data-decoration-slot="genre-books-flowers" aria-hidden="true"><LibraryBig /><Sprout /></span>)}
    {isBiography ? <p className={biography ? 'reader-biography' : 'reader-module-empty'}>{biography || 'Aún no hay una biografía. Este espacio está reservado para una historia lectora.'}</p> : <PreferenceTags values={genres} empty="Aún no has elegido géneros que te representen." />}
    <ProfileEditModal open={editable && editing} title={`Editar ${title}`} icon={isBiography ? <BookOpen /> : <LibraryBig />} description={isBiography ? 'Cuenta tu historia lectora en un máximo de 200 caracteres.' : 'Elige hasta cinco géneros que te representen.'}
      dirty={initial !== JSON.stringify(isBiography ? draft : genreIds)} busy={busy} saveDisabled={isBiography ? length > 200 : genreIds.length > 5 || !options} onSubmit={save} onClose={() => { setEditing(false); setError('') }}>
      {isBiography && <><label htmlFor="profile-biography">Tu biografía</label>
      <textarea id="profile-biography" value={draft} rows={5} disabled={busy} onChange={event => setDraft(event.target.value)} aria-describedby="biography-count biography-visibility" />
      <span id="biography-count" className={length > 200 ? 'reader-field-error' : 'reader-field-count'} aria-live="polite">{length}/200 caracteres</span></>}
      {!isBiography && !options && !catalogError && <p role="status">Cargando géneros…</p>}
      {!isBiography && catalogError && <div><p className="reader-field-error" role="alert">{catalogError}</p><button className="reader-edit-button" type="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></div>}
      {!isBiography && options && <GenreSelector options={availableGenres} selected={genreIds} onToggle={toggleGenre} disabled={busy} />}
      <p id={isBiography ? 'biography-visibility' : undefined}>Visible para toda la comunidad de LibrIAverse.</p>
      {error && <p className="reader-field-error" role="alert">{error}</p>}
    </ProfileEditModal>
    {message && <p className="reader-save-status" role="status">{message}</p>}
  </section>
}
