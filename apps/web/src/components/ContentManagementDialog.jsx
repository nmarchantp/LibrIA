import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { apiRequest } from '../api/client'
import PostComposer from './PostComposer'
import ReviewEditForm from './ReviewEditForm'
import './ContentManagement.css'

export default function ContentManagementDialog({ target,onClose,onSaved }) {
  const dialog=useRef(null),sending=useRef(false)
  const { item,action }=target
  const review=item.feed_item_type==='review'
  const [loaded,setLoaded]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  const [confirmEventDelete,setConfirmEventDelete]=useState(false)
  useEffect(()=>{const node=dialog.current,opener=document.activeElement,overflow=document.body.style.overflow;document.body.style.overflow='hidden';node.showModal();const viewport=window.visualViewport;const fit=()=>node.style.setProperty('--management-height',`${viewport?.height||window.innerHeight}px`);fit();viewport?.addEventListener('resize',fit);return()=>{viewport?.removeEventListener('resize',fit);node.close();document.body.style.overflow=overflow;if(opener?.isConnected)opener.focus({preventScroll:true})}},[])
  useEffect(()=>{
    if(action!=='edit')return
    const controller=new AbortController()
    apiRequest(review?`/reviews/${item.id}`:`/posts/${item.id}`,{headers:{Authorization:`Bearer ${localStorage.getItem('libria_token')}`},signal:controller.signal}).then(result=>setLoaded({...item,...result})).catch(cause=>{if(!controller.signal.aborted)setError(cause.message)})
    return()=>controller.abort()
  },[action,item,review])
  async function remove(){
    if(sending.current)return;sending.current=true;setBusy(true);setError('')
    try{await apiRequest(`/${review?'reviews':'posts'}/${item.id}`,{method:'DELETE',headers:{Authorization:`Bearer ${localStorage.getItem('libria_token')}`}});if(item.source==='event')window.dispatchEvent(new Event('libria-events-updated'));onSaved({deleted:true})}
    catch(cause){setError(cause.message||'No se pudo eliminar el contenido.')}
    finally{sending.current=false;setBusy(false)}
  }
  const title=action==='edit'?(review?'Editar reseña':item.source==='event'?'Editar evento':'Editar publicación'):(review?'Ocultar reseña':'Eliminar publicación')
  return createPortal(<dialog ref={dialog} className="content-management-dialog" aria-labelledby="content-management-title" onCancel={event=>{event.preventDefault();if(!busy)onClose()}}><header><h2 id="content-management-title">{title}</h2><button type="button" aria-label="Cerrar edición" disabled={busy} onClick={onClose}><X size={20} /></button></header><div className="content-management-body">{error&&<p role="alert">{error}</p>}{action==='edit'?(loaded?(review?<ReviewEditForm item={loaded} onSaved={onSaved} onBusyChange={setBusy} />:<><PostComposer role={loaded.author_role} profileId={loaded.author_profile_id} initialPost={loaded} onCreated={onSaved} onBusyChange={setBusy} />{loaded.source==='event'&&<section className="event-delete-zone"><button type="button" disabled={busy} onClick={()=>setConfirmEventDelete(true)}>Eliminar publicación</button>{confirmEventDelete&&<div role="alertdialog" aria-label="Confirmar eliminación del evento"><p>¿Eliminar «{loaded.title}»? Dejará de aparecer en el mural y en Eventos. Se conservarán su historial de asistencia y sus interacciones.</p><button type="button" disabled={busy} onClick={()=>setConfirmEventDelete(false)}>Cancelar</button><button type="button" disabled={busy} onClick={remove}>Eliminar evento</button></div>}</section>}</>):!error&&<p role="status">Cargando publicación…</p>):<><p>¿{review?'Ocultar':'Eliminar'} «{item.title||item.book_title||'esta publicación'}»?</p><p>Dejará de mostrarse en el mural junto con sus comentarios e interacciones. Se conservarán los datos relacionados y no se eliminará la obra.</p><footer><button type="button" className="button" disabled={busy} onClick={onClose}>Cancelar</button><button type="button" className="button primary" disabled={busy} onClick={remove}>{busy?'Guardando…':title}</button></footer></>}</div></dialog>,document.body)
}
