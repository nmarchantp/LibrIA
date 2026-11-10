import { useState } from 'react'
import { SquarePen } from 'lucide-react'
import ContentManagementDialog from './ContentManagementDialog'
import './PostComposer.css'

export default function PublicationComposerLauncher({ role,profileId,onCreated }){
  const [selected,setSelected]=useState(null)
  return <><button type="button" className="publication-create-shortcut" onClick={()=>setSelected('news')} aria-haspopup="dialog"><SquarePen size={20} aria-hidden="true" /><span>Crear publicación</span></button>{selected&&<ContentManagementDialog target={{action:'create',initialType:selected,item:{author_role:role,author_profile_id:profileId}}} onClose={()=>setSelected(null)} onSaved={()=>{setSelected(null);onCreated()}} />}</>
}
