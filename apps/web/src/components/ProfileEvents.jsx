import { useEffect, useState } from 'react'
import { BookOpen, CalendarDays, Check, Clock, LockKeyhole, MapPin, Megaphone, Pencil } from 'lucide-react'
import { Link } from 'react-router-dom'
import { apiRequest, apiAssetUrl, apiUrl } from '../api/client'
import { useEventAttendance } from '../context/EventAttendanceContext'
import { EventDate } from './EventPresentation'
import ContentManagementDialog from './ContentManagementDialog'
import './ProfileEvents.css'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
const categories = { meetup: 'Encuentro', fair: 'Feria', book_club: 'Club de lectura', workshop: 'Taller', other: 'Evento' }

function AgendaCard({ item, own, onEdit }) {
  const { details, toggle } = useEventAttendance(item.event_details)
  const [failed, setFailed] = useState(false)
  // Use the existing event presentation source; never change the catalog cover.
  const source = item.custom_book_cover_url || item.images?.[0] || item.book_cover_url
  const image = source?.startsWith('/posts/') ? apiUrl(source) : apiAssetUrl(source)
  const attending = own ? details.attending : item.profile_attending
  return <article className="personal-event-card">
    <div className="personal-event-image">{image && !failed ? <img src={image} alt="" onError={() => setFailed(true)} /> : <BookOpen size={36} aria-hidden="true" />}<EventDate details={details} /></div>
    <div className="personal-event-copy">
      <div className="personal-event-status">{attending && (own ? <button type="button" aria-label="Cancelar asistencia" title={item.profile_organizing ? 'Asistiré · Organizo. Cancelar mi asistencia' : 'Cancelar mi asistencia'} disabled={details.busy} onClick={toggle}><Check size={16} />{details.busy ? 'Actualizando…' : 'Asistiré'}</button> : <span><Check size={16} />Asistiré</span>)}{item.profile_organizing && !attending && <span><Megaphone size={16} />Organizo</span>}</div>
      <span className="personal-event-category" data-category={details.category}>{categories[details.category] || 'Evento'}</span>
      <h3><Link className="personal-event-link" to={`/?category=events&publication=${item.id}`}>{item.title || 'Encuentro literario'}</Link></h3>
      <p><MapPin size={16} aria-hidden="true" />{details.location}</p>
      <p title={details.timezone}><Clock size={16} aria-hidden="true" /><span>{details.start_time}{details.end_time ? ` – ${details.end_time}` : ''}</span></p>
      <p><CalendarDays size={16} aria-hidden="true" /><span>{details.start_date}{details.end_date && details.end_date !== details.start_date ? ` al ${details.end_date}` : ''}</span></p>
      <div className="personal-event-actions">{own && item.can_manage && <button type="button" aria-label="Editar evento" onClick={() => onEdit(item)}><Pencil size={16} /></button>}</div>
      {details.error && <p role="alert">{details.error}</p>}
    </div>
  </article>
}

export default function ProfileEvents({ profileId = 'me', active = true }) {
  const [period, setPeriod] = useState('upcoming'), [participation, setParticipation] = useState('all')
  const [data, setData] = useState(null), [error, setError] = useState(''), [loading, setLoading] = useState(true)
  const [refresh, setRefresh] = useState(0), [offset, setOffset] = useState(0), [editing, setEditing] = useState(null), [saving, setSaving] = useState(false)
  useEffect(() => {
    const update = () => { setOffset(0); setRefresh(value => value + 1) }
    const focus = () => { if (active) update() }
    window.addEventListener('libria-events-updated', update)
    window.addEventListener('libria-event-attendance-updated', update)
    window.addEventListener('focus', focus)
    return () => { window.removeEventListener('libria-events-updated', update); window.removeEventListener('libria-event-attendance-updated', update); window.removeEventListener('focus', focus) }
  }, [active])
  useEffect(() => {
    const controller = new AbortController()
    apiRequest(`/profiles/${profileId}/events?period=${period}&participation=${participation}&offset=${offset}`, { headers: headers(), signal: controller.signal })
      .then(result => { setData(previous => offset ? { ...result, items: [...previous.items, ...result.items] } : result); setError('') })
      .catch(cause => { if (cause.name !== 'AbortError') { setError(cause.message); if (cause.status === 403) setData(null) } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [profileId, period, participation, offset, refresh])
  const change = (setter, value) => { setter(value); setOffset(0); setLoading(true) }
  const privacy = async event => {
    const visibility = event.target.value
    setSaving(true); setError('')
    try { await apiRequest('/profiles/me/events/privacy', { method: 'PATCH', headers: headers(), body: JSON.stringify({ visibility }) }); setData(previous => ({ ...previous, visibility })) }
    catch (cause) { setError(cause.message) }
    finally { setSaving(false) }
  }
  return <section className="personal-events" aria-labelledby="personal-events-title">
    <div className="personal-events-heading"><div><h2 id="personal-events-title"><CalendarDays aria-hidden="true" />Mis eventos</h2><p>Los eventos en los que participaré y los que organizo.</p></div>{data?.is_owner && <label className="personal-events-privacy"><LockKeyhole size={17} aria-hidden="true" /><span>Privacidad:</span><select aria-label="Privacidad de mis eventos" value={data.visibility} disabled={saving} onChange={privacy}><option value="private">Solo yo</option><option value="contacts">Mis contactos</option><option value="public">Público</option></select></label>}</div>
    <div className="personal-events-filters"><div role="group" aria-label="Fecha de eventos">{[['upcoming', 'Próximos'], ['past', 'Pasados']].map(([value, label]) => <button type="button" key={value} aria-pressed={period === value} onClick={() => change(setPeriod, value)}>{label}{data ? ` (${data.counts[value]})` : ''}</button>)}</div>{data?.can_organize && <div role="group" aria-label="Participación">{[['all', 'Todos'], ['attending', 'Asistiré'], ['organizing', 'Organizo']].map(([value, label]) => <button type="button" key={value} aria-pressed={participation === value} onClick={() => change(setParticipation, value)}>{label}</button>)}</div>}</div>
    {error && <p role="alert">{error}</p>}{loading && <p role="status">Cargando eventos…</p>}
    {!loading && data && <>{data.items.length ? <div className="personal-events-grid">{data.items.map(item => <AgendaCard key={item.id} item={item} own={data.is_owner} onEdit={setEditing} />)}</div> : <div className="personal-events-empty"><CalendarDays size={30} /><h3>{period === 'past' ? 'Todavía no tienes eventos anteriores.' : participation === 'organizing' ? 'Aún no has organizado eventos.' : 'Aún no tienes eventos en tu agenda.'}</h3><p>Explora los próximos encuentros literarios y descubre nuevas experiencias.</p><Link to="/events">Explorar eventos</Link></div>}{data.has_more && <button type="button" className="personal-events-more" onClick={() => change(setOffset, data.items.length)}>Cargar más eventos</button>}</>}
    {editing && <ContentManagementDialog target={{ item: editing, action: 'edit' }} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); window.dispatchEvent(new Event('libria-events-updated')) }} />}
  </section>
}
