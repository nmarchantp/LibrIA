import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import FeedCard from './FeedCard'
import { toFeedPost } from '../services/feedService'
import { useActivityInteractions } from '../context/ActivityInteractionContext'

export default function MuralActivityDialog({ item, openComments = false, onClose }) {
  const dialog = useRef(null)
  const interactions = useActivityInteractions(item)
  useEffect(() => {
    const node = dialog.current, opener = document.activeElement, overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    node.showModal()
    const viewport = window.visualViewport
    const fitViewport = () => node.style.setProperty('--activity-viewport-height', `${viewport?.height || window.innerHeight}px`)
    fitViewport()
    viewport?.addEventListener('resize', fitViewport)
    return () => { viewport?.removeEventListener('resize', fitViewport); node.close(); document.body.style.overflow = overflow; if (opener?.isConnected) opener.focus({ preventScroll: true }) }
  }, [])
  const heading = item.feed_item_type === 'reading_event' ? 'Actividad de lectura' : item.feed_item_type === 'review' ? 'Reseña' : 'Publicación'
  return createPortal(<dialog ref={dialog} className="mural-activity-dialog" aria-labelledby="mural-dialog-heading" onCancel={event => { event.preventDefault(); onClose() }}>
    <header className="mural-dialog-heading"><h2 id="mural-dialog-heading">{heading}</h2><button className="mural-dialog-close" aria-label="Cerrar actividad" onClick={onClose}><X size={20} /></button></header>
    <FeedCard post={toFeedPost(item)} interactions={interactions} initialCommentsOpen={openComments} socialDialog />
  </dialog>, document.body)
}
