// Date-only arithmetic uses UTC as a neutral calendar, never to reinterpret event instants.
export const dateKey=date=>date.toISOString().slice(0,10)
export const parseDay=value=>new Date(`${value}T12:00:00Z`)
export const todayInChile=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())
export const dayLabel=value=>parseDay(value).toLocaleDateString('es-CL',{timeZone:'UTC',weekday:'long',day:'numeric',month:'long',year:'numeric'})
export const monthLabel=value=>parseDay(`${value}-01`).toLocaleDateString('es-CL',{timeZone:'UTC',month:'long',year:'numeric'})
export function shiftMonth(month,step){const day=parseDay(`${month}-01`);day.setUTCMonth(day.getUTCMonth()+step);return dateKey(day).slice(0,7)}
export function calendarDays(month){
  const first=parseDay(`${month}-01`)
  const offset=(first.getUTCDay()+6)%7
  first.setUTCDate(first.getUTCDate()-offset)
  const next=parseDay(`${shiftMonth(month,1)}-01`),last=new Date(next);last.setUTCDate(0)
  const count=Math.ceil((offset+last.getUTCDate())/7)*7
  return Array.from({length:count},(_,index)=>{const day=new Date(first);day.setUTCDate(day.getUTCDate()+index);return dateKey(day)})
}
export const eventOnDay=(item,day)=>item.event_details.start_date<=day&&(item.event_details.end_date||item.event_details.start_date)>=day
export const eventCategory={fair:'Feria',book_club:'Club de lectura',workshop:'Taller',meetup:'Encuentro',other:'Otro'}
