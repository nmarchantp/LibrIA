import { useEffect, useId, useState } from 'react'
import { ArrowDown, ArrowUp, Pencil, Star, X } from 'lucide-react'
import TasteIcon from './TasteIcon'
import { profileService } from '../services/profileService'
import IntensityIndicator from './IntensityIndicator'
import ProfileEditModal from './ProfileEditModal'
import './ProfileReadingTastesCard.css'

export default function ProfileReadingTastesCard({ intensities = [], featuredCategoryId = null, editable = false, onSave }) {
  const featured = intensities.find(item => item.id === featuredCategoryId)
  const [editing, setEditing] = useState(false)
  const title = featured ? `Mi nivel de ${featured.name}` : 'Mis gustos'
  const [selected, setSelected] = useState([])
  const [initial, setInitial] = useState('')
  const [featuredId, setFeaturedId] = useState(null)
  const [catalogs, setCatalogs] = useState(null)
  const [catalogError, setCatalogError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const categoryId = useId()
  useEffect(() => {
    if (!editing) return
    let active = true
    setCatalogs(null); setCatalogError('')
    profileService.catalogs().then(data => { if (active) setCatalogs(data) })
      .catch(() => { if (active) setCatalogError('No se pudieron cargar los gustos disponibles.') })
    return () => { active = false }
  }, [editing, attempt])
  const available = (key, saved) => [...(catalogs?.[key] || []), ...saved.filter(item => !catalogs?.[key]?.some(option => option.id === item.id))]
  const categoryOptions = available('intensities', intensities)
  function edit() {
    setSelected(intensities.map(item => ({ category_id: item.id, level: item.level })))
    setFeaturedId(featuredCategoryId)
    setInitial(JSON.stringify({ intensities: intensities.map(item => ({ category_id: item.id, level: item.level })), featured_category_id: featuredCategoryId }))
    setError(''); setEditing(true)
  }
  function move(index, direction) {
    setSelected(current => {
      const next = [...current]
      const target = index + direction
      if (target < 0 || target >= next.length) return current
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }
  function add(id) {
    if (!id) return
    setSelected(current => current.length >= 5 || current.some(item => item.category_id === id) ? current : [...current, { category_id: id, level: 1 }])
  }
  function remove(id) {
    setSelected(current => current.filter(item => item.category_id !== id))
    if (featuredId === id) setFeaturedId(null)
  }
  async function save(event) {
    event.preventDefault()
    if (!catalogs || busy || selected.length > 5 || new Set(selected.map(item => item.category_id)).size !== selected.length || selected.some(item => !Number.isInteger(item.level) || item.level < 1 || item.level > 5)) return
    setBusy(true); setError('')
    try {
      await onSave({ intensities: selected, featured_category_id: selected.some(item => item.category_id === featuredId) ? featuredId : null })
      setEditing(false); setMessage('Tus gustos se guardaron.')
    } catch (cause) { setError(cause.message || 'No se pudieron guardar tus gustos.') }
    finally { setBusy(false) }
  }
  return <section className="reader-personal-card reader-reading-tastes">
    <div className="reader-card-heading"><h2><TasteIcon name={featured?.icon} size={19} aria-hidden="true" />{title}</h2>{editable && <button className="reader-edit-button" type="button" aria-label="Editar Mis gustos" onClick={edit}><Pencil size={15} aria-hidden="true" /><span>Editar</span></button>}</div>
    <p className="reader-card-description">{featured?.id === 'spicy' ? 'Mi nivel de comodidad con contenido romántico explícito.' : featured?.id === 'terror' ? 'La intensidad de miedo que busco en mis lecturas.' : featured?.id === 'romance' ? 'El protagonismo que prefiero para las historias de amor.' : 'La intensidad que busco en esta experiencia de lectura.'}</p><span className="reader-featured-decoration-slot" data-decoration-slot="featured-reading-companion" aria-hidden="true" />
    {featured ? <div className="reader-taste-highlight" aria-label="Gusto destacado"><IntensityIndicator option={featured} level={featured.level} /></div> : <p className="reader-module-empty">{editable ? 'Elige en Editar cuál de tus gustos quieres mostrar aquí. Puedes configurar hasta cinco y destacar uno, o ninguno.' : 'Aún no hay un gusto destacado.'}</p>}
    <ProfileEditModal open={editable && editing} title="Editar Mis gustos" icon={<TasteIcon />} description="Configura hasta cinco experiencias y elige la que quieres mostrar en Sobre mí."
      dirty={initial !== JSON.stringify({ intensities: selected, featured_category_id: featuredId })} busy={busy} saveDisabled={!catalogs} onSubmit={save} onClose={() => { setEditing(false); setError('') }}>
      <p>Elige hasta cinco experiencias y pulsa sus iconos para indicar cuánto buscas de cada una. Se guardarán todas tus valoraciones; solo se mostrará la que elijas destacar.</p>
      <p>Solo un gusto puede mostrarse en Sobre mí. Puedes cambiarlo o no destacar ninguno.</p>
      {!catalogs && !catalogError && <p role="status">Cargando gustos…</p>}
      {catalogError && <div><p role="alert" className="reader-field-error">{catalogError}</p><button type="button" className="reader-edit-button" onClick={() => setAttempt(value => value + 1)}>Reintentar</button></div>}
      <div className="reader-intensity-grid">{selected.map((item, index) => {
        const option = categoryOptions.find(option => option.id === item.category_id)
        if (!option) return null
        return <div className="reader-intensity-item" key={item.category_id}>
          <div className="reader-intensity-heading"><h3>{option.name}</h3><div className="reader-intensity-actions">
            <button type="button" disabled={busy || index === 0} aria-label={`Subir ${option.name}`} onClick={() => move(index, -1)}><ArrowUp size={15} /></button>
            <button type="button" disabled={busy || index === selected.length - 1} aria-label={`Bajar ${option.name}`} onClick={() => move(index, 1)}><ArrowDown size={15} /></button>
            <button type="button" disabled={busy} aria-label={`Quitar ${option.name}`} onClick={() => remove(item.category_id)}><X size={15} /></button>
          </div></div>
          <IntensityIndicator option={option} level={item.level} disabled={busy} onChange={level => setSelected(current => current.map(value => value.category_id === item.category_id ? { ...value, level } : value))} />
          <button className="reader-feature-choice" type="button" disabled={busy} aria-pressed={featuredId === item.category_id} aria-label={`${featuredId === item.category_id ? 'Dejar de mostrar' : 'Mostrar'} ${option.name} en Sobre mí`} onClick={() => setFeaturedId(current => current === item.category_id ? null : item.category_id)}><Star size={14} aria-hidden="true" />Mostrar en Sobre mí</button>
        </div>
      })}</div>
      <label htmlFor={categoryId}>Agregar categoría ({selected.length}/5)</label>
      <select id={categoryId} value="" disabled={busy || !catalogs || selected.length >= 5} onChange={event => add(event.target.value)}>
        <option value="">Selecciona una experiencia</option>{(catalogs?.intensities || []).filter(option => !selected.some(item => item.category_id === option.id)).map(option => <option key={option.id} value={option.id}>{option.name}</option>)}
      </select>
      {!selected.length && <p>No has seleccionado indicadores. Puedes guardar sin elegir ninguno.</p>}
      {error && <p className="reader-field-error" role="alert">{error}</p>}
    </ProfileEditModal>
    {message && <p className="reader-save-status" role="status">{message}</p>}
  </section>
}
