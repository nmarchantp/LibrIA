import { useEffect, useId, useRef, useState } from 'react'
import { presentBookCategories } from './bookCategories'
import './BookCategoryChips.css'

export default function BookCategoryChips({ categories }) {
  const popoverId = useId()
  const popoverRef = useRef(null)
  const [open, setOpen] = useState(false)
  const displayed = presentBookCategories(categories)
  const remaining = displayed.slice(5)

  useEffect(() => {
    if (!open) return
    const close = event => {
      if (event.type === 'scroll' && popoverRef.current?.contains(event.target)) return
      popoverRef.current?.hidePopover()
    }
    window.addEventListener('resize', close)
    window.addEventListener('scroll', close, true)
    return () => {
      window.removeEventListener('resize', close)
      window.removeEventListener('scroll', close, true)
    }
  }, [open])

  const positionPopover = event => {
    const bounds = event.currentTarget.getBoundingClientRect()
    const width = Math.min(300, window.innerWidth - 32)
    const below = window.innerHeight - bounds.bottom - 24
    const popover = popoverRef.current
    popover.style.width = `${width}px`
    popover.style.left = `${Math.max(16, Math.min(bounds.left, window.innerWidth - width - 16))}px`
    popover.style.top = below >= 120 ? `${bounds.bottom + 8}px` : 'auto'
    popover.style.bottom = below >= 120 ? 'auto' : `${window.innerHeight - bounds.top + 8}px`
    popover.style.maxHeight = `${Math.max(60, below >= 120 ? below : bounds.top - 24)}px`
  }

  if (!displayed.length) return null
  return <div className="genre-tags" aria-label="Géneros y tropos del libro">
    {displayed.slice(0, 5).map(category => <span key={category.label} data-family={category.family}>{category.label}</span>)}
    {remaining.length > 0 && <>
      <button type="button" className="genre-tags-more" popoverTarget={popoverId}
        aria-expanded={open} aria-controls={popoverId} onClick={positionPopover}>
        +{remaining.length} más
      </button>
      <div id={popoverId} ref={popoverRef} popover="auto" className="genre-tags-popover"
        aria-label="Más géneros y categorías" onToggle={event => setOpen(event.newState === 'open')}>
        <div className="genre-tags">{remaining.map(category => <span key={category.label} data-family={category.family}>{category.label}</span>)}</div>
      </div>
    </>}
  </div>
}
