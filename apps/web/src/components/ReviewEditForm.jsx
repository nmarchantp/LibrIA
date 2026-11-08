import { useEffect, useRef, useState } from 'react'
import { apiRequest } from '../api/client'
import RatingControl from './RatingControl'
import { ratingDimensions } from '../data/ratingDimensions'

export default function ReviewEditForm({ item,onSaved,onBusyChange }) {
  const [body,setBody]=useState(item.body),[rating,setRating]=useState(item.rating)
  const [dimensions,setDimensions]=useState(item.dimension_ratings||{}),[spoiler,setSpoiler]=useState(item.is_spoiler||false)
  const [busy,setBusy]=useState(false),[error,setError]=useState('')
  useEffect(()=>onBusyChange?.(busy),[busy,onBusyChange])
  const sending=useRef(false)
  async function save(event) {
    event.preventDefault();if(sending.current)return;sending.current=true;setBusy(true);setError('')
    try {const result=await apiRequest(`/reviews/${item.id}`,{method:'PUT',headers:{Authorization:`Bearer ${localStorage.getItem('libria_token')}`},body:JSON.stringify({body:body.trim(),rating,dimension_ratings:Object.fromEntries(Object.entries(dimensions).filter(([,v])=>v!=null)),is_spoiler:spoiler,edition_id:item.edition_id||null,status:'published'})});onSaved(result)}
    catch(cause){setError(cause.message||'No se pudo guardar la reseña.')}
    finally{sending.current=false;setBusy(false)}
  }
  return <form className="mural-review-editor" onSubmit={save}><p>{item.book_title}</p><label>Tu reseña<textarea value={body} onChange={e=>setBody(e.target.value)} maxLength={3000} rows={5} required /></label><label><input type="checkbox" checked={spoiler} onChange={e=>setSpoiler(e.target.checked)} />Contiene spoilers</label><fieldset disabled={busy}><legend>Valoraciones</legend>{ratingDimensions.map(([key,label,Icon,description,color,outlineColor])=><RatingControl key={key} categoryKey={key} label={label} Icon={Icon} description={description} color={color} outlineColor={outlineColor} value={key==='general'?rating:dimensions[key]} onChange={value=>key==='general'?setRating(value):setDimensions(current=>({...current,[key]:value}))} />)}</fieldset>{error&&<p role="alert">{error}</p>}<button className="button primary" disabled={busy||!body.trim()}>{busy?'Guardando…':'Guardar reseña'}</button></form>
}
