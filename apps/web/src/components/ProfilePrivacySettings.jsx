import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import './ProfilePrivacySettings.css'

const sections = [['biography', 'Biografía'], ['genres', 'Géneros favoritos'], ['tropes', 'Temáticas y tropos'], ['intensities', 'Gustos lectores'], ['interests', 'Intereses'], ['favorite_quotes', 'Citas favoritas'], ['library', 'Mi biblioteca'], ['activity', 'Mi actividad'], ['events', 'Mis eventos'], ['analyses', 'Mis an\u00e1lisis']]
export default function ProfilePrivacySettings({ preferences, showSections = false }) {
  const id = useId()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const { data, loading, error, save } = preferences
  async function update(fields) {
    setBusy(true); setMessage(null)
    try { await save(fields); setMessage({ text: 'Privacidad guardada.', tone: 'is-success' }) }
    catch { setMessage({ text: 'No se pudo guardar la privacidad. Intenta nuevamente.', tone: 'is-error' }) }
    finally { setBusy(false) }
  }
  if (loading) return <p role="status">Cargando privacidad…</p>
  if (error || !data) return <p role="alert">No se pudo cargar la privacidad.</p>
  const visible = data.public_sections || []
  return <section className="profile-privacy-settings" aria-labelledby={`${id}-heading`}>
    <header className="privacy-header">
      <div className="privacy-header-copy"><h2 id={`${id}-heading`}>{showSections ? 'Qué muestro en Sobre mí' : 'Privacidad de mi perfil'}</h2><p>Controla qué secciones de tu universo lector pueden ver otros miembros.</p></div>
      <Link className="privacy-profile-link" to={`/profiles/${data.profile_id}?preview=1`}>Ver como otros<ArrowUpRight size={15} aria-hidden="true" /></Link>
    </header>
    <div className="privacy-visibility">
      <div><label htmlFor={`${id}-visibility`}>¿Quién puede ver tu perfil?</label>
        <p id={`${id}-hint`}>{data.profile_visibility === 'private' ? 'Solo las personas a las que sigues pueden ver las secciones elegidas. Los demás verán tu banner, nombre y foto.' : 'Cualquier persona con sesión iniciada podrá ver las secciones que elijas.'}</p></div>
      <select id={`${id}-visibility`} aria-describedby={`${id}-hint`} value={data.profile_visibility} disabled={busy} onChange={event => update({ profile_visibility: event.target.value })}><option value="public">Público</option><option value="private">Privado</option></select>
    </div>
    {showSections && <fieldset className="privacy-sections" disabled={busy}><legend>Secciones que quieres mostrar</legend>
      <div className="privacy-toggles">{sections.map(([section, label]) => {
        const on = visible.includes(section)
        return <label key={section} className={`privacy-toggle${on ? ' is-on' : ''}`}><span>{label}</span>
          <input type="checkbox" role="switch" checked={on} onChange={event => update({ public_sections: event.target.checked ? [...visible, section] : visible.filter(value => value !== section) })} />
          <span className="privacy-switch" aria-hidden="true" /></label>
      })}</div>
    </fieldset>}
    <p className="privacy-note">{showSections ? 'Estos controles solo afectan a Sobre mí. Tus otras pestañas siempre muestran todo tu contenido personal.' : <Link to="/profile?tab=about&sharing=1#profile-sharing">Elegir lo que muestro en Sobre mí</Link>}</p>
    {message && <p className={`privacy-message ${message.tone}`} role={message.tone === 'is-error' ? 'alert' : 'status'}>{message.text}</p>}
  </section>
}
