import { useEffect,useRef,useState } from 'react'
import { CalendarDays,Plus,Sparkles } from 'lucide-react'
import { apiRequest } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { eventsService } from '../services/eventsService'
import useAgendaEvents from '../hooks/useAgendaEvents'
import AgendaMonth,{ AgendaMonthNavigation } from '../components/AgendaMonth'
import AgendaEventCard from '../components/AgendaEventCard'
import MuralCarousel from '../components/MuralCarousel'
import ContentManagementDialog from '../components/ContentManagementDialog'
import { calendarDays,dayLabel,eventOnDay,todayInChile } from '../components/eventCalendar'
import './EventsPage.css'
import './MuralPage.css'

export default function EventsPage(){
  const {user}=useAuth()
  const today=todayInChile()
  const [month,setMonth]=useState(today.slice(0,7)),[view,setView]=useState('month'),[selectedDay,setSelectedDay]=useState(today),[selectedEvent,setSelectedEvent]=useState(null)
  const [refresh,setRefresh]=useState(0),[editing,setEditing]=useState(null),[profile,setProfile]=useState(null),[older,setOlder]=useState(false),[listUpcoming,setListUpcoming]=useState(false)
  const pinned=useRef(false),detailRef=useRef(null)
  const days=calendarDays(month)
  const feed=useAgendaEvents(view==='list'&&listUpcoming?today:days[0],view==='list'&&listUpcoming?null:days.at(-1),refresh)
  const upcoming=useAgendaEvents(today,null,refresh,9)
  useEffect(()=>{
    if(!['admin','autor','libreria','editorial','influencer'].includes(user.role))return
    const controller=new AbortController()
    apiRequest('/profiles/me',{signal:controller.signal,headers:{Authorization:`Bearer ${localStorage.getItem('libria_token')}`}}).then(profiles=>{if(!controller.signal.aborted)setProfile(profiles.find(profile=>profile.kind==='personal' && profile.can_publish!==false)||null)}).catch(()=>{})
    return()=>controller.abort()
  },[user.id,user.role])
  useEffect(()=>{
    const update=()=>{eventsService.clear();setRefresh(value=>value+1)}
    window.addEventListener('libria-events-updated',update);window.addEventListener('focus',update)
    return()=>{window.removeEventListener('libria-events-updated',update);window.removeEventListener('focus',update)}
  },[])
  useEffect(()=>{
    if(feed.loading||pinned.current||listUpcoming)return
    const inMonth=feed.items.filter(item=>item.event_details.start_date.slice(0,7)===month||eventOnDay(item,`${month}-01`))
    const next=inMonth.find(item=>(item.event_details.end_date||item.event_details.start_date)>=today)||inMonth[0]
    setSelectedDay(next?(next.event_details.start_date<`${month}-01`?`${month}-01`:next.event_details.start_date):month===today.slice(0,7)?today:`${month}-01`)
  },[feed.items,feed.loading,month,today,listUpcoming])
  function changeMonth(value){setMonth(value);setListUpcoming(false);setOlder(false);pinned.current=false;setSelectedEvent(null)}
  function selectDay(day){pinned.current=true;setSelectedDay(day);setSelectedEvent(null)}
  function selectEvent(item){pinned.current=true;setMonth(item.event_details.start_date.slice(0,7));setSelectedDay(item.event_details.start_date);setSelectedEvent(item.id);setView('month');setListUpcoming(false);requestAnimationFrame(()=>detailRef.current?.scrollIntoView({block:'nearest',behavior:'smooth'}))}
  function saved(result){
    setEditing(null)
    if(result?.event_details){pinned.current=true;setMonth(result.event_details.start_date.slice(0,7));setSelectedDay(result.event_details.start_date);setSelectedEvent(result.id);setListUpcoming(false)}
    eventsService.clear();setRefresh(value=>value+1)
  }
  const edit=item=>setEditing({item,action:'edit'})
  const dayItems=feed.items.filter(item=>eventOnDay(item,selectedDay))
  const current=dayItems.find(item=>item.id===selectedEvent)||dayItems[0]
  const items=feed.items.filter(item=>listUpcoming||eventOnDay(item,`${month}-01`)||item.event_details.start_date.slice(0,7)===month)
  const visible=items.filter(item=>view!=='list'||older||month!==today.slice(0,7)||(item.event_details.end_date||item.event_details.start_date)>=today)
  const groups=visible.reduce((all,item)=>{(all[item.event_details.start_date]||=[]).push(item);return all},{})
  return <section className="page-width page agenda-page">
    <header className="agenda-header"><div><span className="kicker">AGENDA LITERARIA</span><h1>Eventos que nos reúnen <Sparkles size={28} aria-hidden="true" /></h1><p>Encuentros, ferias y experiencias para compartir con la comunidad lectora.</p></div>
    {profile&&<button type="button" className="agenda-create" onClick={()=>setEditing({action:'create',initialType:'event',item:{author_role:user.role,author_profile_id:profile.id}})}><Plus size={19} aria-hidden="true" />Crear evento</button>}</header>
    {feed.error&&<div className="agenda-error" role="alert">{feed.error}<button className="button" onClick={()=>{eventsService.clear();setRefresh(value=>value+1)}}>Reintentar</button></div>}
    {view==='month'?<div className="agenda-month-layout"><AgendaMonth month={month} items={feed.items} selected={selectedDay} today={today} onDay={selectDay} onMonth={changeMonth} /><section className="agenda-detail" ref={detailRef} aria-label="Detalle del evento"><h2 className="agenda-selected-date">{dayLabel(selectedDay)}</h2>{feed.loading?<p className="agenda-empty" role="status">Cargando eventos…</p>:<>{dayItems.length>1&&<div className="agenda-day-options" role="group" aria-label="Eventos de la fecha">{dayItems.map(item=><button type="button" key={item.id} aria-pressed={current?.id===item.id} onClick={()=>setSelectedEvent(item.id)}>{item.title}</button>)}</div>}{current?<AgendaEventCard item={current} detail onEdit={edit} />:<div className="agenda-empty"><CalendarDays size={36} strokeWidth={1} /><h3>Un día para nuevas historias</h3><p>No hay eventos programados para esta fecha.</p></div>}</>}</section></div>:<>
      <div className="agenda-browse-heading"><AgendaMonthNavigation month={month} onMonth={changeMonth} />{view==='list'&&month===today.slice(0,7)&&!listUpcoming&&<button type="button" className="agenda-text-button" onClick={()=>setOlder(value=>!value)}>{older?'Solo próximos eventos':'Mostrar eventos anteriores'}</button>}{listUpcoming&&<p>Todos los próximos eventos</p>}</div>
      {feed.loading?<p role="status">Cargando eventos…</p>:view==='grid'?<div className="agenda-grid">{visible.map(item=><AgendaEventCard key={item.id} item={item} onEdit={edit} onSelect={selectEvent} />)}</div>:<div className="agenda-list">{Object.entries(groups).map(([date,items])=><section key={date}><h2>{dayLabel(date)}</h2>{items.map(item=><AgendaEventCard key={item.id} item={item} onEdit={edit} onSelect={selectEvent} />)}</section>)}</div>}
    </>}
    {!feed.loading&&!feed.error&&!items.length&&<p className="agenda-month-empty">No hay eventos con fecha confirmada para este mes. Puedes explorar otro mes.</p>}
    {!feed.loading&&view==='list'&&items.length>0&&!visible.length&&<p className="agenda-month-empty">No quedan eventos próximos este mes. Consulta los anteriores o elige otro mes.</p>}
    {feed.more&&<p className="agenda-month-empty">Hay más eventos en este rango. Carga más para completar la agenda.</p>}
    {feed.more&&<button className="button agenda-more" disabled={feed.busy} onClick={feed.loadMore}>{feed.busy?'Cargando…':'Cargar más eventos'}</button>}
    <div className="agenda-upcoming"><MuralCarousel viewAllLabel="Ver todos" title="Próximos eventos" description="Lo que se viene en LibrIAverse." icon={CalendarDays} items={upcoming.items} empty={upcoming.loading?'Buscando próximos encuentros…':upcoming.error?'No se pudieron cargar los próximos eventos.':'Todavía no hay próximos eventos con fecha confirmada.'} onViewAll={()=>{setView('list');setListUpcoming(true);setOlder(false);window.scrollTo({top:0,behavior:'smooth'})}} renderItem={item=><AgendaEventCard upcoming item={item} onEdit={edit} onSelect={selectEvent} />} />{upcoming.error&&<button className="agenda-text-button" onClick={()=>{eventsService.clear();setRefresh(value=>value+1)}}>Reintentar próximos eventos</button>}</div>
    {editing&&<ContentManagementDialog target={editing} onClose={()=>setEditing(null)} onSaved={saved} />}
  </section>
}
