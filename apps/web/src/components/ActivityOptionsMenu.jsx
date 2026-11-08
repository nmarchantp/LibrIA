import { MoreHorizontal } from 'lucide-react'
import { useMuralManagement } from '../context/MuralManagementContext'

export default function ActivityOptionsMenu({ item }) {
  const management=useMuralManagement()
  if(!management||!item?.can_manage)return null
  return <details className="activity-options" onClick={event=>event.stopPropagation()}><summary aria-label="Opciones de la publicación"><MoreHorizontal size={18} /></summary><div><button type="button" onClick={event=>{event.currentTarget.closest('details').open=false;management.edit(item)}}>{item.feed_item_type==='review'?'Editar reseña':'Editar publicación'}</button><button type="button" onClick={event=>{event.currentTarget.closest('details').open=false;management.remove(item)}}>{item.feed_item_type==='review'?'Ocultar reseña':'Eliminar publicación'}</button></div></details>
}
