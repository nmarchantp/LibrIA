import { useEffect, useId, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import './PostGallery.css'

const visibleTiles = 4

// One image is shown whole; several form a grid whose last tile opens the rest.
export default function PostGallery({ images, alt, onOpen, horizontal = false, editorial = false }) {
  const dialogRef = useRef(null)
  const trackRef = useRef(null)
  const trackId = useId()
  const [arrows, setArrows] = useState({ previous:false, next:false })
  const [current, setCurrent] = useState(null)
  const total = images.length
  const open = current !== null
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])
  useEffect(() => {
    const track = trackRef.current
    if (!horizontal || !track) return
    const update = () => setArrows({ previous:track.scrollLeft>1, next:track.scrollLeft+track.clientWidth<track.scrollWidth-2 })
    const observer = new ResizeObserver(update)
    observer.observe(track)
    track.querySelectorAll('img').forEach(img=>observer.observe(img))
    track.addEventListener('scroll',update,{ passive:true })
    track.addEventListener('load',update,true)
    update()
    return () => { observer.disconnect(); track.removeEventListener('scroll',update); track.removeEventListener('load',update,true) }
  }, [horizontal,total])
  if (!total) return null
  const move = step => setCurrent(index => (index + step + total) % total)
  const tiles = horizontal ? images : images.slice(0, visibleTiles)
  const hidden = total - visibleTiles
  const openImage = async index => {
    if (onOpen) {
      try {
        await onOpen()
      } catch {
        // Keep the gallery usable even when the tracking request fails.
      }
    }
    setCurrent(index)
  }

  return <>
    {editorial ? <div className="post-gallery-editorial" style={{ gridTemplateColumns:`repeat(${Math.min(total,4)},minmax(0,1fr))`, maxWidth:Math.min(total,4)*180+(Math.min(total,4)-1)*8 }} aria-label="Fotografías adjuntas">
      {images.slice(0,4).map((src,index)=><button type="button" key={`${index}-${src}`} className="post-gallery-tile" onClick={()=>openImage(index)} aria-label={`Ampliar imagen ${index+1} de ${total}`}><img src={src} alt={`${alt} (${index+1} de ${total})`} loading="lazy" />{index===3&&total>4&&<span className="post-gallery-overflow" aria-hidden="true">+{total-3}</span>}</button>)}
    </div> : <>
    <div className={horizontal ? 'post-gallery-horizontal' : undefined}>
    {horizontal && (arrows.previous || arrows.next) && <div className="post-gallery-controls"><button type="button" aria-label="Fotografías anteriores" aria-controls={trackId} disabled={!arrows.previous} onClick={()=>trackRef.current.scrollBy({left:-trackRef.current.clientWidth*.8,behavior:'smooth'})}><ChevronLeft size={18} /></button><button type="button" aria-label="Fotografías siguientes" aria-controls={trackId} disabled={!arrows.next} onClick={()=>trackRef.current.scrollBy({left:trackRef.current.clientWidth*.8,behavior:'smooth'})}><ChevronRight size={18} /></button></div>}
    <div ref={trackRef} id={trackId} tabIndex={horizontal ? 0 : undefined} aria-label={horizontal ? 'Fotografías adjuntas' : undefined} className={`post-gallery count-${Math.min(total, visibleTiles)}`}>
      {tiles.map((src, index) => {
        const more = !horizontal && index === visibleTiles - 1 && hidden > 0
        return <button type="button" key={`${index}-${src}`} className="post-gallery-tile" onClick={() => openImage(index)}
          aria-label={more ? `Ver las ${total} imágenes` : `Ampliar imagen ${index + 1} de ${total}`}>
          <img src={src} alt={`${alt} (${index + 1} de ${total})`} loading="lazy" />
          {more && <span className="post-gallery-more" aria-hidden="true"><strong>+{hidden}</strong>Ver todas ({total})</span>}
        </button>
      })}
    </div>
    </div>
    </>}
    <dialog ref={dialogRef} className="post-lightbox" aria-label="Imágenes de la publicación" onClose={() => { if(!dialogRef.current?.open)setCurrent(null) }}
      onClick={event => { if (event.target === event.currentTarget) setCurrent(null) }}
      onKeyDown={event => { if (event.key === 'ArrowRight') move(1); if (event.key === 'ArrowLeft') move(-1) }}>
      {open && <div className="post-lightbox-frame">
        <button type="button" className="post-lightbox-close" aria-label="Cerrar" onClick={() => setCurrent(null)}><X aria-hidden="true" /></button>
        <figure>
          <img src={images[current]} alt={`${alt} (${current + 1} de ${total})`} />
          <figcaption aria-live="polite">{current + 1} / {total}</figcaption>
        </figure>
        {total > 1 && <>
          <button type="button" className="post-lightbox-nav is-prev" aria-label="Imagen anterior" onClick={() => move(-1)}><ChevronLeft aria-hidden="true" /></button>
          <button type="button" className="post-lightbox-nav is-next" aria-label="Imagen siguiente" onClick={() => move(1)}><ChevronRight aria-hidden="true" /></button>
          <div className="post-lightbox-thumbs">{images.map((src, index) => <button type="button" key={`${index}-${src}`} className={index === current ? 'active' : ''} aria-label={`Ver imagen ${index + 1}`} aria-current={index === current} onClick={() => setCurrent(index)}><img src={src} alt="" /></button>)}</div>
        </>}
      </div>}
    </dialog>
  </>
}
