import { useRef, useState } from 'react'
import ContentReportButton from './ContentReportButton'

export default function CommentEntry({ comment, userId, roleLabel, showAvatar, readingEvent, onSave, onDelete }) {
  const [editing,setEditing]=useState(false),[removing,setRemoving]=useState(false),[text,setText]=useState(comment.body)
  const [busy,setBusy]=useState(false),[error,setError]=useState('')
  const sending=useRef(false),editVersion=useRef(comment.moderation_version)
  const words=text.trim()?text.trim().split(/\s+/u).length:0
  const invalid=readingEvent?words>200:text.length>1000
  async function run(action){
    if(sending.current)return;sending.current=true;setBusy(true);setError('')
    try{await action();setEditing(false);setRemoving(false)}catch(cause){setError(cause.message||'No se pudo guardar el cambio.')}finally{sending.current=false;setBusy(false)}
  }
  const own=comment.user_id===userId&&onSave&&onDelete
  return <div className="comment-item">
    {showAvatar&&<span className="mural-comment-avatar" aria-hidden="true">{comment.author.split(' ').slice(0,2).map(word=>word[0]).join('')}</span>}
    <div className="comment-content"><div className="comment-meta"><div className="comment-author"><strong>{comment.author}</strong><span className={`user-role-badge role-${comment.author_role}`}>{roleLabel}</span></div><time dateTime={comment.created_at}>{new Date(comment.created_at).toLocaleString('es-CL',{dateStyle:'short'})}</time>{own&&<details className="activity-options"><summary aria-label="Opciones de tu comentario">•••</summary><div><button type="button" onClick={event=>{event.currentTarget.closest('details').open=false;editVersion.current=comment.moderation_version;setText(comment.body);setError('');setEditing(true)}}>Editar</button><button type="button" onClick={event=>{event.currentTarget.closest('details').open=false;setError('');setRemoving(true)}}>Eliminar</button></div></details>}</div>
    {editing?<form className="comment-inline-editor" onSubmit={event=>{event.preventDefault();run(()=>onSave(comment.id,text.trim(),editVersion.current))}}><textarea aria-label="Editar comentario" value={text} onChange={e=>setText(e.target.value)} maxLength={readingEvent?undefined:1000} rows={3} required /><small>{readingEvent?`${words}/200 palabras`:`${text.length}/1000`}</small><div><button disabled={busy||invalid||!text.trim()}>{busy?'Guardando…':'Guardar'}</button><button type="button" disabled={busy} onClick={()=>setEditing(false)}>Cancelar</button></div></form>:<p>{comment.body}</p>}
    {comment.edited_at&&!editing&&<small className="comment-edited" title={new Date(comment.edited_at).toLocaleString('es-CL')}>Editado</small>}
    {removing&&<div className="comment-remove-confirm" role="alertdialog" aria-label="Eliminar comentario"><p>¿Eliminar tu comentario?</p><button type="button" disabled={busy} onClick={()=>run(()=>onDelete(comment.id))}>Eliminar</button><button type="button" disabled={busy} onClick={()=>setRemoving(false)}>Cancelar</button></div>}
    <ContentReportButton kind="comment" identifier={comment.id} />
    {error&&<p className="comment-error" role="alert">{error}</p>}</div>
  </div>
}
