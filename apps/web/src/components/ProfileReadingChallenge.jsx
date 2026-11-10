import { useEffect, useRef, useState } from 'react'
import { BookHeart, BookOpen, CalendarDays, Info, Pencil, Sparkles, Target } from 'lucide-react'
import { apiRequest } from '../api/client'
import ProfileEditModal from './ProfileEditModal'
import './ProfileReadingChallenge.css'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })

export default function ProfileReadingChallenge() {
  const [data, setData] = useState(null), [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0), [editing, setEditing] = useState(false)
  const [target, setTarget] = useState('12'), [initial, setInitial] = useState('12')
  const [busy, setBusy] = useState(false), [saveError, setSaveError] = useState('')
  const sending = useRef(false), requestVersion = useRef(0)
  useEffect(() => {
    let timer
    const update = () => { clearTimeout(timer); timer = setTimeout(() => setRefresh(value => value + 1), 100) }
    const events = ['libria:book-activity-changed', 'libria:catalog-identity-changed', 'focus']
    events.forEach(name => window.addEventListener(name, update))
    return () => { clearTimeout(timer); events.forEach(name => window.removeEventListener(name, update)) }
  }, [])
  useEffect(() => {
    const controller = new AbortController(), version = ++requestVersion.current
    apiRequest('/me/reading-challenge', { headers: headers(), signal: controller.signal })
      .then(result => { if (version === requestVersion.current) { setData(result); setError('') } })
      .catch(cause => { if (cause.name !== 'AbortError' && version === requestVersion.current) setError(cause.message) })
    return () => controller.abort()
  }, [refresh])
  function edit() {
    const value = String(data.target || 12)
    setTarget(value); setInitial(value); setSaveError(''); setEditing(true)
  }
  async function save(event) {
    event.preventDefault()
    if (sending.current) return
    const value = Number(target)
    if (!/^\d+$/.test(target) || !Number.isInteger(value) || value < 1 || value > 1000) { setSaveError('Elige un número entero entre 1 y 1000 libros.'); return }
    sending.current = true; setBusy(true); setSaveError(''); ++requestVersion.current
    try {
      const result = await apiRequest('/me/reading-challenge', { method: 'PUT', headers: headers(), body: JSON.stringify({ target: value }) })
      ++requestVersion.current
      setData(result); setError(''); setEditing(false)
    } catch (cause) { setSaveError(cause.message || 'No se pudo guardar tu reto.') }
    finally { sending.current = false; setBusy(false) }
  }
  const valid = /^\d+$/.test(target) && Number(target) >= 1 && Number(target) <= 1000
  return <section className="reader-personal-card reading-challenge" data-stage={!data?.target ? 'start' : data.completed ? 'complete' : 'progress'} aria-labelledby="reading-challenge-title">
    <div className="reader-card-heading"><h2 id="reading-challenge-title"><Target size={19} aria-hidden="true" />Mi reto de lectura</h2>{data?.target && (data.completed ? <button className="reading-challenge-year-pill" type="button" aria-label="Editar meta anual" title="Editar meta anual" onClick={edit}><CalendarDays size={14} aria-hidden="true" />{data.year}</button> : <span className="reading-challenge-year-pill"><CalendarDays size={14} aria-hidden="true" />{data.year}</span>)}</div>
    {error && <div><p role="alert">{error}</p><button type="button" className="reading-challenge-action" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></div>}
    {!data && !error && <p role="status">Cargando tu reto…</p>}
    {data && (data.target ? <div className="reading-challenge-progress" aria-live="polite">
      {!data.completed && <div className="reading-challenge-summary"><span className="reading-challenge-book" aria-hidden="true"><BookHeart /></span><div><p className="reading-challenge-count"><strong>{data.finished_books}</strong> de {data.target} libros</p><p className="reading-challenge-percentage">{data.percentage} % completado</p></div><button className="reader-edit-button" type="button" aria-label="Editar meta anual" onClick={edit}><Pencil size={14} /></button></div>}
      {data.completed && <div className="reading-challenge-celebration"><img className="reading-challenge-art is-complete" src="/images/challenge-complete-lettered.png" alt="¡Reto completado!" /></div>}
      {data.completed && <p className="reading-challenge-count"><strong>{data.finished_books}</strong> de {data.target} libros</p>}
      {data.completed && <p className="reading-challenge-result">{data.exceeded ? '¡Meta superada!' : '¡Reto completado!'}</p>}
      <progress max="100" value={data.percentage} aria-label={`${data.percentage} % del reto anual completado`} />
      {data.completed ? <div className="reading-challenge-completed"><img src="/images/challenge-badge.png" alt="" aria-hidden="true" /><div><strong>Reto lector {data.year}</strong><span>Has completado tu meta anual de lectura.</span></div></div> : <><p className="reading-challenge-remaining"><BookOpen size={17} aria-hidden="true" />{data.remaining} {data.remaining === 1 ? 'libro restante' : 'libros restantes'}</p><div className="reading-challenge-encouragement"><Sparkles className="reading-challenge-sparkles" size={23} aria-hidden="true" /><div><strong>¡Vas muy bien!</strong><p>Tu meta está cada vez más cerca.</p></div><img className="reading-challenge-art is-progress" src="/images/challenge-progress.png" alt="" aria-hidden="true" /></div></>}
    </div> : <><img className="reading-challenge-art is-start" src="/images/challenge-start.png" alt="" aria-hidden="true" /><h3>Cada gran aventura comienza con una página</h3><p className="reader-module-empty">Elige cuántos libros quieres leer este año y sigue tu progreso</p><button type="button" className="reading-challenge-action" onClick={edit}>Crear mi reto</button></>)}
    <ProfileEditModal open={editing} className="reading-challenge-modal" saveLabel="Guardar reto" title="Configurar mi reto de lectura" icon={<Target size={28} />} description="Elige cuántos libros quieres leer este año." dirty={target !== initial} busy={busy} saveDisabled={!valid} onClose={() => setEditing(false)} onSubmit={save}>
      <div className="reading-challenge-suggestions" role="group" aria-label="Metas sugeridas">{[5, 12, 20, 30, 50].map(value => <button type="button" key={value} disabled={busy} aria-label={`${value} libros`} aria-pressed={Number(target) === value} onClick={() => setTarget(String(value))}><BookOpen size={16} aria-hidden="true" />{value}</button>)}</div>
      <label className="reading-challenge-custom" htmlFor="reading-challenge-target"><span>O ingresa una cantidad personalizada:</span><input id="reading-challenge-target" type="number" min="1" max="1000" step="1" inputMode="numeric" required value={target} disabled={busy} onChange={event => setTarget(event.target.value)} aria-describedby="reading-challenge-limit" title="Entre 1 y 1000 libros" /></label>
      <div className="reading-challenge-help" id="reading-challenge-limit"><Info size={18} aria-hidden="true" /><p>Puedes modificar tu meta en cualquier momento durante el año sin perder tu progreso.</p></div>{saveError && <p role="alert">{saveError}</p>}
    </ProfileEditModal>
  </section>
}
