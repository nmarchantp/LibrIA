import { useEffect,useRef,useState } from 'react'
import { eventsService } from '../services/eventsService'

export default function useAgendaEvents(from,to,refresh,limit=100){
  const range=`${from||''}:${to||''}:${limit}`
  const identity=`${from||''}:${to||''}:${refresh}:${limit}`
  const current=useRef(identity);current.current=identity
  const [state,setState]=useState({identity,range,items:[],loading:true,error:'',more:false,busy:false})
  const loadingMore=useRef(false)
  useEffect(()=>{
    const controller=new AbortController()
    setState(previous=>previous.range===range?{...previous,identity,loading:!previous.items.length,error:''}:{identity,range,items:[],loading:true,error:'',more:false,busy:false})
    eventsService.page({from,to,limit},controller.signal).then(data=>{if(!controller.signal.aborted)setState({identity,range,items:data.items,more:data.has_more,loading:false,error:'',busy:false})}).catch(error=>{if(!controller.signal.aborted)setState(previous=>({...previous,identity,range,loading:false,error:error.message,busy:false}))})
    return()=>controller.abort()
  },[from,to,refresh,limit,identity,range])
  async function loadMore(){
    if(loadingMore.current||state.loading||!state.more)return
    loadingMore.current=true;setState(value=>({...value,busy:true,error:''}))
    try{const data=await eventsService.page({from,to,offset:state.items.length,limit});if(current.current===identity)setState(value=>({...value,items:[...value.items,...data.items.filter(item=>!value.items.some(previous=>previous.id===item.id))],more:data.has_more,busy:false}))}
    catch(error){if(current.current===identity)setState(value=>({...value,busy:false,error:error.message}))}
    finally{loadingMore.current=false}
  }
  return {...(state.identity===identity?state:state.range===range?{...state,identity,loading:!state.items.length,error:''}:{identity,range,items:[],loading:true,error:'',more:false,busy:false}),loadMore}
}
