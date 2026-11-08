import { useEffect, useId, useRef, useState } from 'react'
import { ArrowRight, ChevronLeft, ChevronRight } from 'lucide-react'

export default function MuralCarousel({ title, description, icon: Icon, items, onViewAll, renderItem, empty }) {
  const track = useRef(null)
  const heading = useId()
  const trackId = useId()
  const [edges, setEdges] = useState({ start: true, end: true })
  useEffect(() => {
    const node = track.current
    if (!node) return
    const update = () => setEdges({ start: node.scrollLeft < 2, end: node.scrollLeft + node.clientWidth >= node.scrollWidth - 2 })
    const observer = new ResizeObserver(update)
    observer.observe(node)
    node.addEventListener('scroll', update, { passive: true })
    update()
    return () => { observer.disconnect(); node.removeEventListener('scroll', update) }
  }, [items])
  function move(direction) {
    const node = track.current
    node.scrollBy({ left: direction * node.clientWidth * .9, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
  }
  return <section className="mural-category" aria-labelledby={heading}>
    <header className="mural-category-heading"><span className="mural-category-icon"><Icon size={25} strokeWidth={1.5} aria-hidden="true" /></span><div><h2 id={heading}>{title}</h2><p>{description}</p></div><button className="mural-view-all" onClick={onViewAll}>Ver todo <ArrowRight size={16} aria-hidden="true" /></button></header>
    {items.length ? <div className="mural-carousel-wrap">
      <button className="mural-carousel-arrow previous" aria-label={`Anterior: ${title}`} aria-controls={trackId} disabled={edges.start} onClick={() => move(-1)}><ChevronLeft size={20} /></button>
      <div ref={track} id={trackId} className="mural-carousel-track" role="region" aria-label={title} tabIndex={0} onKeyDown={event => {
        if (event.target !== event.currentTarget) return
        if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); move(event.key === 'ArrowRight' ? 1 : -1) }
        if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); track.current.scrollTo({ left: event.key === 'Home' ? 0 : track.current.scrollWidth }) }
      }}>{items.map(item => <div className="mural-carousel-slide" key={`${item.feed_item_type}:${item.id}`}>{renderItem(item)}</div>)}</div>
      <button className="mural-carousel-arrow next" aria-label={`Siguiente: ${title}`} aria-controls={trackId} disabled={edges.end} onClick={() => move(1)}><ChevronRight size={20} /></button>
    </div> : <p className="mural-category-empty">{empty}</p>}
  </section>
}
