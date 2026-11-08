import { useEffect,useState } from 'react'
import { MapPin,Pencil,Users } from 'lucide-react'
import { apiRequest } from '../api/client'
import { EventDate,EventAttendanceButton,EventInformation } from '../components/EventPresentation'
import ContentManagementDialog from '../components/ContentManagementDialog'

const labels={fair:'Feria',book_club:'Club de lectura',workshop:'Taller',meetup:'Encuentro',other:'Otro'}
export default function EventsPage(){
  const [items,setItems]=useState([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[more,setMore]=useState(false),[refresh,setRefresh]=useState(0)
  const [editing,setEditing]=useState(null),[message,setMessage]=useState('')
  useEffect(()=>{
    const controller=new AbortController();setLoading(true);setError('')
    apiRequest('/events',{headers:{Authorization:`Bearer ${localStorage.getItem('libria_token')}`},signal:controller.signal}).then(data=>{if(!controller.signal.aborted){setItems(data.items);setMore(data.has_more)}}).catch(cause=>{if(!controller.signal.aborted)setError(cause.message)}).finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    return()=>controller.abort()
  },[refresh])
  useEffect(()=>{const update=()=>setRefresh(value=>value+1);window.addEventListener('libria-events-updated',update);window.addEventListener('focus',update);return()=>{window.removeEventListener('libria-events-updated',update);window.removeEventListener('focus',update)}},[])
  async function loadMore(){setLoading(true);setError('');try{const data=await apiRequest(`/events?offset=${items.length}`,{headers:{Authorization:`Bearer ${localStorage.getItem('libria_token')}`}});setItems(current=>[...current,...data.items.filter(item=>!current.some(existing=>existing.id===item.id))]);setMore(data.has_more)}catch(cause){setError(cause.message)}finally{setLoading(false)}}
  return <section className="page-width page community-page"><span className="kicker">COMUNIDAD LITERARIA</span><h1 className="page-title">Eventos que nos reúnen</h1><p className="page-lead">Descubre ferias, clubes de lectura y encuentros cerca de ti.</p><div className="community-grid">{items.map(item=><article className="community-card event-card" key={item.id}>
    <EventDate details={item.event_details} /><div><span className="pill-label">{labels[item.event_details.category]}</span><h2>{item.title}</h2><p><MapPin size={15} />{item.event_details.location}</p><p><Users size={15} />{item.event_details.organizer}</p><EventInformation details={item.event_details} showLocation={false} showSchedule /></div><div className="calendar-event-actions"><EventAttendanceButton details={item.event_details} />{item.can_manage&&<button type="button" className="event-edit-button" aria-label="Editar evento" title="Editar evento" onClick={()=>setEditing({item,action:'edit'})}><Pencil size={20} /></button>}</div>
  </article>)}</div>{message&&<p role="status">{message}</p>}{loading&&<p role="status">Cargando eventos…</p>}{error&&<p role="alert">{error}<button className="button" onClick={()=>setRefresh(value=>value+1)}>Reintentar</button></p>}{!loading&&!error&&!items.length&&<p>Todavía no hay eventos con fecha confirmada.</p>}{more&&<button className="button" disabled={loading} onClick={loadMore}>Cargar más eventos</button>}{editing&&<ContentManagementDialog target={editing} onClose={()=>setEditing(null)} onSaved={result=>{setEditing(null);setMessage(result?.deleted?'Evento eliminado.':'Cambios guardados.');setRefresh(value=>value+1)}} />}</section>
}
