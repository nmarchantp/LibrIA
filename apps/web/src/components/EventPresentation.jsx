import { CalendarDays,Check,MapPin,Users } from 'lucide-react'
import { useEventAttendance } from '../context/EventAttendanceContext'
import './EventPresentation.css'

const months=['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC']
export function EventDate({ details }){
  const {details:current}=useEventAttendance(details)
  const [year,month,day]=(current?.start_date||'').split('-')
  return <div className="event-date" aria-label={year?`Fecha del evento: ${day} de ${months[Number(month)-1]} de ${year}`:'Evento sin fecha confirmada'}><strong>{day||'—'}</strong><span>{year?months[Number(month)-1]:'SIN FECHA'}</span></div>
}

export function EventAttendanceButton({ details,showCount=true }){
  const {details:current,toggle}=useEventAttendance(details)
  return <div className="event-attendance"><button type="button" className={`event-attend-button${current?.attending?' is-attending':''}`} aria-label={current?.attending?'Cancelar asistencia':'Quiero asistir'} aria-pressed={Boolean(current?.attending)} aria-busy={current?.busy||false} disabled={!current||current.busy} title={!current?'Completa la fecha del evento para habilitar inscripciones':current.attending?'Cancelar mi asistencia':'Confirmar mi asistencia'} onClick={event=>{event.stopPropagation();toggle()}}>{current?.attending?<Check size={18} />:<CalendarDays size={18} />}{current?.busy?'Actualizando…':current?.attending?'Asistiré':'Quiero asistir'}</button>{showCount&&current&&<small>{current.attendee_count} {current.attendee_count===1?'asistente':'asistentes'}</small>}{current?.error&&<p role="alert">{current.error}</p>}</div>
}

export function EventInformation({ details,showLocation=true,showSchedule=false,showUpdate=showSchedule }){
  const {details:current}=useEventAttendance(details)
  if(!current)return <p className="event-missing-date">Fecha por confirmar. El evento aún no aparece en el calendario.</p>
  const format=(instant,zone)=>new Date(instant).toLocaleString('es-CL',{timeZone:zone})
  const update=current.schedule_update
  return <div className="event-information">{showLocation&&<p><MapPin size={16} aria-hidden="true" />{current.location}<span aria-hidden="true">·</span><Users size={16} aria-hidden="true" />{current.organizer}</p>}{showSchedule&&<p>{current.start_time}{current.end_time?` – ${current.end_date!==current.start_date?`${current.end_date} `:''}${current.end_time}`:''} · {current.timezone}</p>}{showUpdate&&update&&<details className="event-schedule-update"><summary>Fecha u horario actualizado</summary><p>{showSchedule&&<>Actualizado el {format(update.changed_at,current.timezone)}. Antes: {format(update.previous_start,update.previous_timezone)}{update.previous_end?` – ${format(update.previous_end,update.previous_timezone)}`:''}. </>}La asistencia ya confirmada se conserva.</p></details>}</div>
}

export function EventAttendanceCount({ details }){
  const {details:current}=useEventAttendance(details)
  if(!current)return null
  return <span className="event-attendee-count" aria-label={`${current.attendee_count} asistentes`}><Users size={17} aria-hidden="true" /><span>Asistentes</span><span>{current.attendee_count}</span></span>
}
