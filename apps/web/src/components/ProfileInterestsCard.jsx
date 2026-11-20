import { useEffect, useId, useState } from 'react'
import { Compass, Pencil } from 'lucide-react'
import { profileService } from '../services/profileService'
import PreferenceTags from './PreferenceTags'
import ProfileEditModal from './ProfileEditModal'

const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim()

export default function ProfileInterestsCard({ interests = [], editable = false, onSave }) {
  const id = useId()
  const [editing, setEditing] = useState(false)
  const [selected, setSelected] = useState([])
  const [initial, setInitial] = useState('')
  const [options, setOptions] = useState(null)
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [catalogError, setCatalogError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [message, setMessage] = useState('')
  useEffect(() => {
    if (!editing) return
    let active = true
    setOptions(null); setCatalogError('')
    profileService.catalogs().then(data => { if (active) setOptions(data.interests) })
      .catch(() => { if (active) setCatalogError('No se pudieron cargar los intereses.') })
    return () => { active = false }
  }, [editing, attempt])
  function edit() {
    const ids = interests.map(item => item.id)
    setSelected(ids); setInitial(JSON.stringify([...ids].sort()))
    setQuery(''); setError(''); setEditing(true)
  }
  async function save(event) {
    event.preventDefault()
    if (busy || !options) return
    setBusy(true); setError('')
    try {
      await onSave({ interest_ids: selected })
      setEditing(false); setMessage('Intereses guardados.')
    } catch (cause) { setError(cause.message || 'No se pudieron guardar tus intereses.') }
    finally { setBusy(false) }
  }
  const available = [...(options || []), ...interests.filter(item => !options?.some(option => option.id === item.id))]
  const groups = new Map()
  for (const option of available) {
    if (!normalize(option.name).includes(normalize(query))) continue
    const group = option.group || 'Otros intereses'
    if (!groups.has(group)) groups.set(group, [])
    groups.get(group).push(option)
  }
  return <section className="reader-personal-card reader-interests">
    <div className="reader-card-heading"><h2><Compass size={19} aria-hidden="true" />Mis intereses</h2>{editable && <button className="reader-edit-button" type="button" aria-label="Editar mis intereses" onClick={edit}><Pencil size={15} aria-hidden="true" /></button>}</div>
    <p className="reader-card-description">Los temas que despiertan mi curiosidad.</p>
    <PreferenceTags values={interests} empty={editable ? 'Usa el lápiz para elegir tus intereses.' : 'Aún no hay intereses seleccionados.'} />
    <ProfileEditModal open={editable && editing} title="Editar mis intereses" icon={<Compass />} description="Elige los temas que te interesan. Puedes seleccionar varios o quitar los que ya no te representan."
      dirty={initial !== JSON.stringify([...selected].sort())} busy={busy} saveDisabled={!options} onSubmit={save} onClose={() => setEditing(false)}>
      {!options && !catalogError && <p role="status">Cargando intereses…</p>}
      {catalogError && <div><p role="alert">{catalogError}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></div>}
      {options && <fieldset disabled={busy}><legend>Mis intereses ({selected.length})</legend>
        <label className="reader-trope-search" htmlFor={`${id}-search`}>Buscar intereses<input id={`${id}-search`} type="search" value={query} onChange={event => setQuery(event.target.value)} /></label>
        <div className="reader-preference-options">{[...groups].map(([group, values]) => <div className="reader-trope-group" key={group} role="group" aria-label={group}><h4>{group}</h4>{values.map(option => <label key={option.id}><input type="checkbox" checked={selected.includes(option.id)} onChange={() => setSelected(current => current.includes(option.id) ? current.filter(value => value !== option.id) : [...current, option.id])} /><span>{option.name}</span></label>)}</div>)}</div>
        {!groups.size && <p>No hay intereses que coincidan con la búsqueda.</p>}
      </fieldset>}
      <p>Puedes elegir si se muestran a otros usuarios al editar «Mi universo literario».</p>
      {error && <p role="alert">{error}</p>}
    </ProfileEditModal>
    {message && <p className="reader-save-status" role="status">{message}</p>}
  </section>
}
