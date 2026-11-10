import { MoreHorizontal } from 'lucide-react'
import { useMuralManagement } from '../context/MuralManagementContext'
import ContentReportButton from './ContentReportButton'

export default function ActivityOptionsMenu({ item }) {
  const management=useMuralManagement()
  const kind=item?.feed_item_type==='review'?'review':'publication'
  if(!item||!['publication','review'].includes(item.feed_item_type))return null
  return <details className="activity-options" onClick={event=>event.stopPropagation()}><summary aria-label="Opciones de la publicación"><MoreHorizontal size={18} /></summary><div>{management&&item.can_manage&&<><button type="button" onClick={event=>{event.currentTarget.closest('details').open=false;management.edit(item)}}>{kind==='review'?'Editar reseña':'Editar publicación'}</button><button type="button" onClick={event=>{event.currentTarget.closest('details').open=false;management.remove(item)}}>{kind==='review'?'Ocultar reseña':'Eliminar publicación'}</button></>}<ContentReportButton kind={kind} identifier={item.id} menu /></div></details>
}
