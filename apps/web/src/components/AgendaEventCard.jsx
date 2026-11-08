import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen,CalendarDays,Clock,MapPin,Pencil,Users } from 'lucide-react'
import { apiAssetUrl,apiUrl } from '../api/client'
import { EventAttendanceButton,EventAttendanceCount,EventDate,EventInformation } from './EventPresentation'
import { eventCategory } from './eventCalendar'

function EventImage({ sources,title }){
  const [index,setIndex]=useState(0)
  const src=sources[index]
  return <div className="agenda-event-image">{src?<img src={src} alt={`Imagen de ${title}`} loading="lazy" onError={()=>setIndex(value=>value+1)} />:<BookOpen size={42} strokeWidth={1} aria-label="Evento sin imagen disponible" />}</div>
}

export default function AgendaEventCard({ item,detail=false,upcoming=false,onEdit,onSelect }){
  const details=item.event_details
  const images=[...new Set((detail||upcoming?[item.custom_book_cover_url,item.book_cover_url,item.images?.[0]]:[item.images?.[0],item.custom_book_cover_url,item.book_cover_url]).filter(Boolean).map(value=>value.startsWith('/posts/')?apiUrl(value):apiAssetUrl(value)))]
  return <article className={`agenda-event event-card${detail?' is-detail':''}${upcoming?' is-upcoming':''}`} data-event-id={item.id}>
    {!detail&&<EventDate details={details} />}
    <EventImage key={images.join('|')||'placeholder'} sources={images} title={item.title} />
    {upcoming&&<div className="agenda-upcoming-attendance"><EventAttendanceButton details={details} showCount={false} /></div>}
    <div className="agenda-event-copy"><div className="agenda-event-heading"><span className="agenda-category" data-category={details.category}>{eventCategory[details.category]||'Encuentro'}</span>{!upcoming&&item.can_manage&&<button type="button" className="event-edit-button" aria-label="Editar evento" title="Editar evento" onClick={()=>onEdit(item)}><Pencil size={19} /></button>}</div>
      <h2>{upcoming?<Link className="agenda-upcoming-original" to={`/?category=events&publication=${encodeURIComponent(item.id)}`} title={`Ver publicación: ${item.title}`}>{item.title}</Link>:onSelect?<button type="button" onClick={()=>onSelect(item)} title={item.title}>{item.title}</button>:item.title}</h2>
      <p className="agenda-event-meta"><MapPin size={15} aria-hidden="true" />{details.location}</p>
      {detail&&<p className="agenda-event-meta"><Users size={15} aria-hidden="true" />{details.organizer}</p>}
      <p className="agenda-event-meta"><Clock size={15} aria-hidden="true" /><span>{details.start_time}{details.end_time?` – ${details.end_time}`:''}{detail?` (${details.timezone})`:''}</span></p>
      {(upcoming||(details.end_date&&details.end_date!==details.start_date))&&<p className="agenda-event-range">{upcoming&&<CalendarDays size={15} aria-hidden="true" />}<span>{details.start_date}{details.end_date&&details.end_date!==details.start_date?` al ${details.end_date}`:''}</span></p>}
      {detail&&<><p className="agenda-event-description">{item.body}</p><EventInformation details={details} showLocation={false} showSchedule={false} showUpdate /></>}
      {!upcoming&&<div className="agenda-event-actions"><EventAttendanceButton details={details} showCount={false} />{detail&&<EventAttendanceCount details={details} />}</div>}
    </div>
  </article>
}
