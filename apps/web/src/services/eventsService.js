import { apiRequest } from '../api/client'

const cache=new Map()
const invalidate=()=>cache.clear()
window.addEventListener('libria-events-updated',invalidate)
if(import.meta.hot)import.meta.hot.dispose(()=>window.removeEventListener('libria-events-updated',invalidate))
export const eventsService={
  async page({from,to,offset=0,limit=100},signal){
    const params=new URLSearchParams({limit:String(limit),offset:String(offset),...(from?{from_date:from}:{}),...(to?{to_date:to}:{})})
    const key=params.toString(),token=localStorage.getItem('libria_token'),cacheKey=`${token}:${key}`,previous=cache.get(cacheKey)
    if(previous&&Date.now()-previous.at<30000)return previous.data
    const data=await apiRequest(`/events?${key}`,{signal,headers:{Authorization:`Bearer ${token}`}})
    if(!signal?.aborted){if(cache.size>=12)cache.delete(cache.keys().next().value);cache.set(cacheKey,{data,at:Date.now()})}
    return data
  },
  clear(){cache.clear()},
}
