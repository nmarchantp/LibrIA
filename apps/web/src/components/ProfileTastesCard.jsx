import { useEffect, useState } from 'react'
import { BookHeart, LibraryBig, Pencil, Sprout } from 'lucide-react'
import { profileService } from '../services/profileService'
import PreferenceTags from './PreferenceTags'
import ProfileEditModal from './ProfileEditModal'

const groupOrder = ['Romance y relaciones', 'Fantasía y magia', 'Misterio y suspenso', 'Aventura y ciencia ficción', 'Personajes y emociones']
const searchable = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim()

export default function ProfileTastesCard({ tropes = [], editable = false, onSave }) {
  const [editing, setEditing] = useState(false)
  const [catalogs, setCatalogs] = useState(null)
  const [tropeIds, setTropeIds] = useState([])
  const [initial, setInitial] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [catalogError, setCatalogError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')
  useEffect(() => {
    if (!editing) return
    let active = true
    setCatalogs(null); setCatalogError('')
    profileService.catalogs().then(data => { if (active) setCatalogs(data) })
      .catch(() => { if (active) setCatalogError('No se pudieron cargar las opciones.') })
    return () => { active = false }
  }, [editing, attempt])
  function edit() {
    setTropeIds(tropes.map(x => x.id))
    setInitial(JSON.stringify(tropes.map(x => x.id).sort()))
    setError(''); setSearch(''); setEditing(true)
  }
  function toggle(id, selected, setSelected, maximum) {
    if (selected.includes(id)) setSelected(selected.filter(value => value !== id))
    else if (!maximum || selected.length < maximum) setSelected([...selected, id])
  }
  async function save(event) {
    event.preventDefault()
    if (!catalogs || busy) return
    setBusy(true); setError('')
    try { await onSave({ trope_ids: tropeIds }); setEditing(false); setMessage('Gustos literarios guardados.') }
    catch (cause) { setError(cause.message || 'No se pudieron guardar tus gustos.') }
    finally { setBusy(false) }
  }
  // Keep already saved, retired options visible so they can be retained or removed.
  const options = (key, saved) => [...(catalogs?.[key] || []), ...saved.filter(value => !catalogs?.[key].some(x => x.id === value.id))]
  const grouped = new Map()
  for (const option of options('tropes', tropes)) {
    if (!searchable(option.name).includes(searchable(search))) continue
    const group = option.group || 'Otras temáticas'
    if (!grouped.has(group)) grouped.set(group, [])
    grouped.get(group).push(option)
  }
  const groups = [...grouped].sort(([a], [b]) => {
    const rank = value => groupOrder.includes(value) ? groupOrder.indexOf(value) : groupOrder.length
    return rank(a) - rank(b) || a.localeCompare(b, 'es')
  })
  return <section className="reader-personal-card reader-tastes">
    <div className="reader-card-heading"><h2><BookHeart size={19} aria-hidden="true" />Mis temáticas y tropos favoritos</h2>{editable && <button className="reader-edit-button" type="button" aria-label="Editar temáticas y tropos" onClick={edit}><Pencil size={15} aria-hidden="true" /><span>Editar</span></button>}</div>
    <p className="reader-card-description">Las temáticas que siempre me llaman y los tropos que me hacen amar una historia.</p><span className="reader-card-decoration" data-decoration-slot="trope-books-flowers" aria-hidden="true"><LibraryBig /><Sprout /></span>
    <PreferenceTags values={tropes} empty="Aún no hay temáticas o tropos seleccionados." />
    <ProfileEditModal open={editable && editing} title="Editar temáticas y tropos" icon={<BookHeart />} description="Elige las temáticas y los tropos que disfrutas en tus lecturas." dirty={initial !== JSON.stringify([...tropeIds].sort())} busy={busy} saveDisabled={!catalogs} onSubmit={save} onClose={() => { setEditing(false); setError('') }}>
      <p>Estas preferencias son visibles para toda la comunidad.</p>
      {!catalogs && !catalogError && <p role="status">Cargando opciones…</p>}
      {catalogError && <div><p className="reader-field-error" role="alert">{catalogError}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></div>}
      {catalogs && <>
        <fieldset disabled={busy}><legend>Temáticas y tropos favoritos ({tropeIds.length})</legend>
          <label className="reader-trope-search" htmlFor="trope-search">Buscar por nombre<input id="trope-search" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Por ejemplo: magia, segunda oportunidad…" /></label>
          <div className="reader-preference-options">{groups.map(([group, values]) => <div className="reader-trope-group" key={group} role="group" aria-label={group}><h4>{group}</h4>{values.map(option => <label key={option.id}><input type="checkbox" checked={tropeIds.includes(option.id)} onChange={() => toggle(option.id, tropeIds, setTropeIds)} /><span>{option.name}</span></label>)}</div>)}</div>
          {!groups.length && <p role="status">No hay temáticas que coincidan con la búsqueda.</p>}
        </fieldset>
      </>}
      {error && <p className="reader-field-error" role="alert">{error}</p>}
    </ProfileEditModal>
    {message && <p className="reader-save-status" role="status">{message}</p>}
  </section>
}
