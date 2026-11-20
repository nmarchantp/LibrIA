import { useRef, useState } from 'react'
import { GripVertical } from 'lucide-react'

export default function ReorderableProfileCards({ cards, order = [], editable, onSave }) {
  const [draft, setDraft] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [dragging, setDragging] = useState(null)
  const [target, setTarget] = useState(null)
  const moving = useRef(false)
  const ids = [...new Set([...(draft || order), ...cards.map(card => card.id)])].filter(id => cards.some(card => card.id === id))
  async function move(from, to) {
    if (moving.current || from === to || !ids.includes(to)) return
    const previous = draft
    const next = ids.filter(id => id !== from)
    next.splice(ids.indexOf(to), 0, from)
    moving.current = true
    setBusy(true); setDraft(next); setMessage('Guardando orden…')
    try {
      await onSave({ card_order: next })
      setMessage('Orden guardado.')
    } catch {
      setDraft(previous); setMessage('No se pudo guardar el orden. Intenta nuevamente.')
    } finally { moving.current = false; setBusy(false) }
  }
  return <>
    {editable && <p className="reader-reorder-help">Arrastra desde el control de cada card para cambiar su lugar. Con el teclado, usa las flechas sobre el control.</p>}
    <div className="reader-about-grid reader-about-grid--sortable" aria-busy={busy}>
      {ids.map(id => {
        const card = cards.find(item => item.id === id)
        return <div key={id} data-profile-card={id} className={`reader-sortable-card${card.wide ? ' is-wide' : ''}${editable ? ' is-reorderable' : ''}${dragging === id ? ' is-dragging' : ''}${target === id && dragging !== id ? ' is-drop-target' : ''}`}>
          {editable && <button type="button" className="reader-card-drag-handle" disabled={busy} aria-label={`Mover ${card.label}. Usa las flechas para cambiar su posición.`}
            onPointerDown={event => {
              if (event.button !== 0) return
              event.preventDefault(); event.currentTarget.focus()
              event.currentTarget.setPointerCapture(event.pointerId)
              setDragging(id); setTarget(id)
            }}
            onPointerMove={event => {
              if (!event.currentTarget.hasPointerCapture(event.pointerId)) return
              const hit = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-profile-card]')
              setTarget(hit?.dataset.profileCard || null)
              if (event.clientY > window.innerHeight - 70) window.scrollBy(0, 15)
              else if (event.clientY < 70) window.scrollBy(0, -15)
            }}
            onPointerUp={event => {
              if (!event.currentTarget.hasPointerCapture(event.pointerId)) return
              const hit = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-profile-card]')
              event.currentTarget.releasePointerCapture(event.pointerId)
              setDragging(null); setTarget(null)
              if (hit) move(id, hit.dataset.profileCard)
            }}
            onPointerCancel={() => { setDragging(null); setTarget(null) }}
            onKeyDown={event => {
              if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return
              event.preventDefault()
              const offset = ['ArrowUp', 'ArrowLeft'].includes(event.key) ? -1 : 1
              const destination = ids[ids.indexOf(id) + offset]
              if (destination) move(id, destination)
            }}><GripVertical size={18} aria-hidden="true" /><span>Mover</span></button>}
          {card.content}
        </div>
      })}
    </div>
    <p className="reader-save-status" role="status">{message}</p>
  </>
}
