import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import './PostGallery.css'

const visibleTiles = 4

// One image is shown whole; several form a grid whose last tile opens the rest.
export default function PostGallery({ images, alt }) {
  const dialogRef = useRef(null)
  const [current, setCurrent] = useState(null)
  const total = images.length
  const open = current !== null
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])
  if (!total) return null
  const move = step => setCurrent(index => (index + step + total) % total)
  const tiles = images.slice(0, visibleTiles)
  const hidden = total - visibleTiles

  return <>
    <div className={`post-gallery count-${Math.min(total, visibleTiles)}`}>
      {tiles.map((src, index) => {
        const more = index === visibleTiles - 1 && hidden > 0
        return <button type="button" key={`${index}-${src}`} className="post-gallery-tile" onClick={() => setCurrent(index)}
          aria-label={more ? `Ver las ${total} imágenes` : `Ampliar imagen ${index + 1} de ${total}`}>
          <img src={src} alt={`${alt} (${index + 1} de ${total})`} loading="lazy" />
          {more && <span className="post-gallery-more" aria-hidden="true"><strong>+{hidden}</strong>Ver todas ({total})</span>}
        </button>
      })}
    </div>
    <dialog ref={dialogRef} className="post-lightbox" aria-label="Imágenes de la publicación" onClose={() => setCurrent(null)}
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
