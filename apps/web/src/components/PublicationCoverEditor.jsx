import { useRef, useState } from 'react'
import { apiRequest, apiUrl } from '../api/client'
import PublicationCoverPicker from './PublicationCoverPicker'

export default function PublicationCoverEditor({ postId, currentUrl, catalogUrl, onSaved }) {
  const [open,setOpen]=useState(false),[mode,setMode]=useState(currentUrl?'custom':'catalog')
  const [file,setFile]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const saving=useRef(false)
  async function save(event) {
    event.preventDefault()
    if(saving.current)return
    saving.current=true
    setBusy(true);setError('')
    try {
      if(mode==='custom'&&!file) {setOpen(false);return}
      const form=new FormData()
      if(file)form.append('book_cover',file)
      const result=await apiRequest(`/posts/${postId}/book-cover`,{method:mode==='custom'?'PUT':'DELETE',headers:{Authorization:`Bearer ${localStorage.getItem('libria_token')}`},...(mode==='custom'?{body:form}:{})})
      onSaved(result.custom_book_cover_url ? apiUrl(result.custom_book_cover_url) : null)
      setFile(null);setOpen(false)
    } catch(cause){setError(cause.message||'No se pudo guardar la portada. Inténtalo de nuevo.')}
    finally{saving.current=false;setBusy(false)}
  }
  return <div className="publication-cover-edit">{open ? <form onSubmit={save}>
    <PublicationCoverPicker mode={mode} onModeChange={setMode} file={file} onChange={setFile} currentUrl={currentUrl} catalogUrl={catalogUrl} disabled={busy} />
    {error&&<p className="comment-error" role="alert">{error}</p>}
    <footer><button disabled={busy||(mode==='custom'&&!file&&!currentUrl)}>{busy?'Guardando…':'Guardar portada'}</button><button type="button" disabled={busy} onClick={()=>{setOpen(false);setFile(null)}}>Cancelar</button></footer>
  </form> : <button type="button" onClick={()=>{setMode(currentUrl?'custom':'catalog');setError('');setOpen(true)}}>Cambiar portada</button>}</div>
}
