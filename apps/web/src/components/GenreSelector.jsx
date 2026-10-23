import { useId, useState } from 'react'
import { X } from 'lucide-react'

const searchable = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim()

export default function GenreSelector({ options, selected, onToggle, disabled = false }) {
  const [search, setSearch] = useState('')
  const searchId = useId()
  const selectedOptions = selected
    .map(id => options.find(option => option.id === id))
    .filter(Boolean)
    .sort((a, b) => Array.from(a.name).length - Array.from(b.name).length || a.name.localeCompare(b.name, 'es'))
  const visibleOptions = options
    .filter(option => searchable(option.name).includes(searchable(search)))
    .sort((a, b) => a.name.localeCompare(b.name, 'es'))
  return <fieldset disabled={disabled}>
    <legend>Géneros que me representan ({selected.length}/5)</legend>
    {selectedOptions.length ? <ul className="reader-selected-genres" aria-label="Géneros seleccionados">{selectedOptions.map(option => <li key={option.id}>
      <span>{option.name}</span>
      <button type="button" disabled={disabled} onClick={() => onToggle(option.id)} aria-label={`Quitar ${option.name}`}><X size={13} aria-hidden="true" /></button>
    </li>)}</ul> : <p>Aún no has seleccionado géneros.</p>}
    <label className="reader-trope-search" htmlFor={searchId}>Buscar géneros<input id={searchId} type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Por ejemplo: fantasía, romance…" /></label>
    <p>Elige libremente hasta cinco géneros, incluidos varios tipos de romance. La búsqueda conserva tu selección.</p>
    <div className="reader-preference-options">{visibleOptions.map(option => <label key={option.id}><input type="checkbox" checked={selected.includes(option.id)} disabled={!selected.includes(option.id) && selected.length >= 5} onChange={() => onToggle(option.id)} /><span>{option.name}</span></label>)}</div>
    {!visibleOptions.length && <p role="status">No hay géneros que coincidan con la búsqueda.</p>}
  </fieldset>
}
