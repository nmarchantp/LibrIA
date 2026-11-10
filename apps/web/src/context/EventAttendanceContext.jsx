import { createContext,useContext,useEffect,useMemo,useSyncExternalStore } from 'react'
import { apiRequest } from '../api/client'

const Context=createContext(null)
function createStore(){
  const entries=new Map(),listeners=new Set()
  const notify=()=>listeners.forEach(listener=>listener())
  const get=details=>{
    if(!details)return null
    if(!entries.has(details.id))entries.set(details.id,{...details,busy:false,error:''})
    return entries.get(details.id)
  }
  const apply=(id,data)=>{
    const previous=entries.get(id)
    if(previous?.observed_at&&data.observed_at&&data.observed_at<previous.observed_at)return
    entries.set(id,{...previous,...data,error:''});notify()
  }
  const request=(id,method='GET')=>apiRequest(`/events/${id}/attendance`,{method,headers:{Authorization:`Bearer ${localStorage.getItem('libria_token')}`}})
  return {get,subscribe:listener=>{listeners.add(listener);return()=>listeners.delete(listener)},
    seed(details){if(!details)return;const previous=get(details);if(details.observed_at>previous.observed_at&&!previous.busy)apply(details.id,details)},
    async refresh(){await Promise.allSettled(Array.from(entries.keys(),async id=>{try{apply(id,await request(id))}catch{/* Stale cards cannot authorize a mutation; the server checks again. */}}))},
    async toggle(details){
      const value=get(details);if(!value||value.busy)return
      entries.set(details.id,{...value,busy:true,error:''});notify()
      try{apply(details.id,await request(details.id,value.attending?'DELETE':'PUT'));window.dispatchEvent(new Event('libria-event-attendance-updated'))}
      catch(cause){entries.set(details.id,{...entries.get(details.id),error:cause.message||'No se pudo actualizar la asistencia.'})}
      finally{entries.set(details.id,{...entries.get(details.id),busy:false});notify()}
    },
  }
}

export function EventAttendanceProvider({ children }) {
  const store=useMemo(createStore,[])
  useEffect(()=>{
    const refresh=()=>store.refresh()
    window.addEventListener('focus',refresh)
    window.addEventListener('libria-events-updated',refresh)
    return()=>{window.removeEventListener('focus',refresh);window.removeEventListener('libria-events-updated',refresh)}
  },[store])
  return <Context.Provider value={store}>{children}</Context.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useEventAttendance(details){
  const store=useContext(Context)
  const value=useSyncExternalStore(store?.subscribe||(()=>()=>{}),()=>store?store.get(details):details||null)
  useEffect(()=>{store?.seed(details)},[store,details])
  return {details:value,toggle:()=>store?.toggle(details)}
}
