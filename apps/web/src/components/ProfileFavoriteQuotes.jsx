import { useState } from 'react'
import { ChevronLeft, ChevronRight, Heart, Pencil, Quote, Sprout } from 'lucide-react'
import ProfileEditModal from './ProfileEditModal'
import './ProfileFavoriteQuotes.css'

export default function ProfileFavoriteQuotes({ editable = false, quotes = [], loading, error, onRetry, onSave }) {
  const [index, setIndex] = useState(0)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState([])
  const [initial, setInitial] = useState('')
  const [busy, setBusy] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [message, setMessage] = useState('')
  const entries = quotes.map(quote => typeof quote === 'string' ? { text: quote, source: '' } : quote)
  const active = Math.min(index, Math.max(0, quotes.length - 1))
  function edit() {
    const fields = Array.from({ length: 4 }, (_, i) => entries[i] || { text: '', source: '' })
    setDraft(fields); setInitial(JSON.stringify(fields)); setSaveError(''); setEditing(true)
  }
  async function save(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setSaveError('')
    try {
      await onSave({ favorite_quotes: draft.map(value => ({ text: value.text.trim(), source: value.source.trim() })).filter(value => value.text) })
      setIndex(0); setEditing(false); setMessage('Tus citas favoritas se han guardado.')
    } catch (cause) { setSaveError(cause.message || 'No se pudieron guardar tus citas. Intenta nuevamente.') }
    finally { setBusy(false) }
  }
  return <section className="reader-personal-card reader-favorite-quotes" aria-label="Mis citas favoritas">
    <div className="reader-card-heading"><h2><Quote size={23} aria-hidden="true" />Mis citas favoritas</h2>{editable && <button className="reader-edit-button" type="button" aria-label="Editar mis citas favoritas" disabled={loading || !!error} onClick={edit}><Pencil size={14} aria-hidden="true" /></button>}</div>
    <p>Frases que me inspiran, me acompañan o simplemente amo.</p>
    {loading ? <p role="status">Cargando tus citas…</p> : error ? <div><p role="alert">{error}</p><button type="button" className="reader-edit-button" onClick={onRetry}>Reintentar</button></div> : quotes.length ? <>
      <div className="reader-quotes-carousel" role="region" aria-roledescription="carrusel" aria-label="Citas favoritas">
        <button type="button" disabled={quotes.length < 2} aria-label="Cita anterior" onClick={() => setIndex((active + quotes.length - 1) % quotes.length)}><ChevronLeft size={18} /></button>
        <div className="reader-quote-slide" aria-live="polite" aria-atomic="true"><blockquote>“{entries[active].text}” <Heart size={16} aria-hidden="true" /></blockquote><span className="reader-quote-position">{entries[active].source}</span></div>
        <button type="button" disabled={quotes.length < 2} aria-label="Cita siguiente" onClick={() => setIndex((active + 1) % quotes.length)}><ChevronRight size={18} /></button>
      </div>
      <div className="reader-quote-dots" aria-label="Elegir una cita">{quotes.map((_, i) => <button key={i} type="button" aria-label={`Ver cita ${i + 1}`} aria-current={active === i ? 'true' : undefined} onClick={() => setIndex(i)} />)}</div>
    </> : <div className="reader-quotes-empty"><Quote aria-hidden="true" /><p>Aún no has añadido citas. Edita este espacio y guarda hasta cuatro frases favoritas.</p></div>}
    <Sprout className="reader-quotes-flower" size={45} strokeWidth={1} aria-hidden="true" />
    {message && <p className="reader-save-status" role="status">{message}</p>}
    <ProfileEditModal open={editing} title="Mis citas favoritas" icon={<Quote />} description="Agrega hasta cuatro frases de 300 caracteres cada una. Deja un campo vacío para quitar una cita." dirty={initial !== JSON.stringify(draft)} busy={busy} onClose={() => setEditing(false)} onSubmit={save}>
      {draft.map((value, i) => <div className="reader-quote-field" key={i}><label htmlFor={`favorite-quote-${i}`}>Cita {i + 1}</label><textarea id={`favorite-quote-${i}`} rows={3} maxLength={300} value={value.text} disabled={busy} onChange={event => setDraft(current => current.map((text, position) => position === i ? { ...text, text: event.target.value } : text))} /><span className="reader-field-count">{value.text.length}/300</span><label htmlFor={`favorite-quote-source-${i}`}>Autor, personaje o libro (opcional)</label><input id={`favorite-quote-source-${i}`} type="text" maxLength={150} value={value.source} placeholder="Ej.: Elizabeth Bennet - Orgullo y prejuicio" disabled={busy} onChange={event => setDraft(current => current.map((quote, position) => position === i ? { ...quote, source: event.target.value } : quote))} /></div>)}
      {saveError && <p className="reader-field-error" role="alert">{saveError}</p>}
    </ProfileEditModal>
  </section>
}
