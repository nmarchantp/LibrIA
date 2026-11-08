import { ChevronLeft,ChevronRight } from 'lucide-react'
import { calendarDays,dayLabel,eventOnDay,monthLabel } from './eventCalendar'

export function AgendaMonthNavigation({month,onMonth}){
  function shift(step){const [year,index]=month.split('-').map(Number),date=new Date(Date.UTC(year,index-1+step,1,12));onMonth(date.toISOString().slice(0,7))}
  return <div className="agenda-month-navigation"><button type="button" aria-label="Mes anterior" onClick={()=>shift(-1)}><ChevronLeft size={20} /></button><label><span>{monthLabel(month)}</span><input type="month" value={month} aria-label="Elegir mes y año" min="1900-01" max="2100-12" onChange={event=>{if(event.target.value)onMonth(event.target.value)}} /></label><button type="button" aria-label="Mes siguiente" onClick={()=>shift(1)}><ChevronRight size={20} /></button></div>
}

export default function AgendaMonth({month,items,selected,today,onDay,onMonth}){
  const days=calendarDays(month)
  return <section className="agenda-calendar" aria-label="Calendario de eventos"><AgendaMonthNavigation month={month} onMonth={onMonth} /><div className="agenda-calendar-week" aria-hidden="true">{['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'].map(day=><span key={day}>{day}</span>)}</div><div className="agenda-calendar-days">{days.map(day=>{
    const count=items.filter(item=>eventOnDay(item,day)).length
    return <button type="button" key={day} data-day={day} className={`${day.slice(0,7)!==month?'is-adjacent ':''}${day===selected?'is-selected ':''}${day===today?'is-today':''}`} aria-pressed={day===selected} aria-current={day===today?'date':undefined} aria-label={`${dayLabel(day)}${count?`, ${count} ${count===1?'evento':'eventos'}`:', sin eventos'}`} onClick={()=>onDay(day)}><span>{Number(day.slice(-2))}</span>{count>0&&<small aria-hidden="true">{count===1?'•':count}</small>}</button>
  })}</div></section>
}
