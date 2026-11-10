export default function EventFields({ value,onChange,required,disabled }){
  const field=(key,next)=>onChange({...value,[key]:next})
  const zones=['America/Santiago','America/Punta_Arenas','UTC']
  return <fieldset className="composer-event-fields" disabled={disabled}><legend>Datos del evento</legend>
    <label>Fecha de inicio<input name="event_start_date" type="date" value={value.start_date} required={required} onChange={e=>field('start_date',e.target.value)} /></label>
    <label>Hora de inicio<input name="event_start_time" type="time" value={value.start_time} required={required} onChange={e=>field('start_time',e.target.value)} /></label>
    <label>Fecha de término (opcional)<input name="event_end_date" type="date" value={value.end_date||''} min={value.start_date||undefined} required={Boolean(value.end_time)} onChange={e=>field('end_date',e.target.value)} /></label>
    <label>Hora de término (opcional)<input name="event_end_time" type="time" value={value.end_time||''} required={Boolean(value.end_date)} onChange={e=>field('end_time',e.target.value)} /></label>
    <label>Lugar<input name="event_location" value={value.location} maxLength={300} required={required} onChange={e=>field('location',e.target.value)} /></label>
    <label>Organizador<input name="event_organizer" value={value.organizer} maxLength={200} required={required} onChange={e=>field('organizer',e.target.value)} /></label>
    <label>Categoría<select name="event_category" value={value.category} onChange={e=>field('category',e.target.value)}><option value="fair">Feria</option><option value="book_club">Club de lectura</option><option value="workshop">Taller</option><option value="meetup">Encuentro</option><option value="other">Otro</option></select></label>
    <label>Zona horaria<select name="event_timezone" value={value.timezone} onChange={e=>field('timezone',e.target.value)}>{[...new Set([...zones,value.timezone])].map(zone=><option key={zone}>{zone}</option>)}</select></label>
    <p>Las horas se guardan en la zona seleccionada, respetando sus cambios de horario.{!required&&' Este evento antiguo no tiene fecha confirmada; completa estos datos para incorporarlo al calendario.'}</p>
  </fieldset>
}
