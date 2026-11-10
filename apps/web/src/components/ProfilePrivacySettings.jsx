import { useState } from 'react'
import { Link } from 'react-router-dom'

const sections = [['biography', 'Biografía'], ['genres', 'Géneros favoritos'], ['tropes', 'Temáticas y tropos'], ['intensities', 'Gustos lectores'], ['interests', 'Intereses'], ['favorite_quotes', 'Citas favoritas']]
export default function ProfilePrivacySettings({ preferences }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const { data, loading, error, save } = preferences
  async function update(fields) {
    setBusy(true); setMessage('')
    try { await save(fields); setMessage('Privacidad guardada.') }
    catch { setMessage('No se pudo guardar la privacidad. Intenta nuevamente.') }
    finally { setBusy(false) }
  }
  if (loading) return <p role="status">Cargando privacidad…</p>
  if (error || !data) return <p role="alert">No se pudo cargar la privacidad.</p>
  return <section className="reader-personal-card profile-privacy-settings" aria-label="Privacidad de mi perfil"><h2>Privacidad de mi perfil</h2>
    <label>¿Quién puede ver tu perfil?<select value={data.profile_visibility} disabled={busy} onChange={event => update({ profile_visibility: event.target.value })}><option value="public">Público</option><option value="private">Privado</option></select></label>
    <p>{data.profile_visibility === 'private' ? 'Solo las personas a las que sigues pueden ver las secciones elegidas. Los demás verán tu banner, nombre y foto.' : 'Cualquier persona con sesión iniciada puede ver las secciones que elijas.'}</p>
    <fieldset disabled={busy}><legend>Secciones que quieres mostrar</legend>{sections.map(([id, label]) => <label key={id}><input type="checkbox" checked={(data.public_sections || []).includes(id)} onChange={event => update({ public_sections: event.target.checked ? [...(data.public_sections || []), id] : (data.public_sections || []).filter(value => value !== id) })} />{label}</label>)}</fieldset>
    <p>La agenda conserva su propia privacidad en «Mis eventos» y respeta el bloqueo del perfil privado.</p>
    <Link to={`/profiles/${data.profile_id}`}>Ver mi perfil comunitario</Link>{message && <p role="status">{message}</p>}
  </section>
}
