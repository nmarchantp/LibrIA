import { X } from 'lucide-react'
import { apiAssetUrl } from '../api/client'
import BookCover from './BookCover'

export default function LiteraryCoverStack({ books, onRemove, onSelect, activeId, className = '' }) {
  return <div className={`registration-cover-stack ${className}`}>
    {books.map((item, index) => {
      const author = [...new Set(item.authors || [])].join(', ')
      const cover = <BookCover large book={{ title: item.title, author, image: apiAssetUrl(item.cover_url), initial: item.title[0], color: '#654184', accent: '#fff4db' }} />
      return <figure key={item.id} className={`registration-stacked-book${activeId === item.id ? ' is-active' : ''}`} title={`${item.title}${author ? ` · ${author}` : ''}`}
        style={{ '--stack-angle': `${(index - (books.length - 1) / 2) * 3}deg`, '--stack-order': index }}>
        {onSelect ? <button type="button" className="registration-cover-select" aria-label={`Ver recomendación: ${item.title}`} aria-pressed={activeId === item.id} onClick={() => onSelect(item.id)}>{cover}</button> : cover}
        {onRemove && <button type="button" className="registration-remove-favorite" aria-label={`Quitar ${item.title} de favoritos`} onClick={() => onRemove(item.id)} title={`Quitar ${item.title}`}><X size={16} aria-hidden="true" /></button>}
        <figcaption className="registration-stack-caption">{item.title}{author && ` · ${author}`}</figcaption>
      </figure>
    })}
  </div>
}
