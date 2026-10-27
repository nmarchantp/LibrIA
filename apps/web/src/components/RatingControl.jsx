import { useId, useState } from 'react'
import { X } from 'lucide-react'
import PartialRatingIcon from './PartialRatingIcon'
import BattlesRatingIcon from './BattlesRatingIcon'

const formatScore = value => Number(value).toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 2 })

export default function RatingControl({ categoryKey, label, Icon, value, onChange, description, color, outlineColor }) {
  const descriptionId = useId()
  const [preview, setPreview] = useState(null)
  const displayed = preview ?? value
  const selected = value != null && value > 0
  const icon = (filled, darkOutline = false) => {
    const stroke = filled ? 'none' : darkOutline ? 'var(--rating-category-outline-color)' : 'var(--rating-category-color)'
    if (categoryKey === 'battles') return <BattlesRatingIcon selected={filled} strokeColor={stroke} />
    return ['world_building', 'spicy'].includes(categoryKey)
    ? <Icon selected={filled} strokeColor={stroke} />
    : <Icon className={filled ? 'rating-category-fill' : undefined} aria-hidden="true" stroke={stroke} strokeWidth={0.7} strokeLinecap="round" strokeLinejoin="round" fill="none"
      style={{ stroke, strokeWidth: 0.7, fill: 'none', opacity: 1 }} />
  }
  const quarterAt = (event, score) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    return score - 1 + Math.max(1, Math.min(4, Math.ceil((event.clientX - bounds.left) / bounds.width * 4))) / 4
  }
  return <div className="library-rating-row" style={{ '--rating-category-color': color, '--rating-star-color': color, '--rating-category-outline-color': outlineColor }}>
    <span className="library-rating-label" title={description} tabIndex={description ? 0 : undefined} aria-describedby={description ? descriptionId : undefined}>
      <Icon aria-hidden="true" strokeWidth={['spicy', 'world_building'].includes(categoryKey) ? 1.5 : 2.1} /><strong>{label}</strong>{description && <span className="library-rating-tooltip" id={descriptionId} role="tooltip">{description} Sin valorar: sin puntuación registrada.</span>}
    </span>
    <span className="library-rating-buttons" role="slider" tabIndex={0} aria-label={`Valoración de ${label}`} aria-valuemin={0} aria-valuemax={5} aria-valuenow={selected ? value : 0}
      aria-valuetext={selected ? `${formatScore(value)} de 5` : 'Sin valorar'} aria-describedby={description ? descriptionId : undefined}
      onPointerLeave={() => setPreview(null)} onBlur={() => setPreview(null)}
      onKeyDown={event => {
        let next
        if (['ArrowRight', 'ArrowUp'].includes(event.key)) next = Math.min(5, (value ?? 0) + 0.25)
        else if (['ArrowLeft', 'ArrowDown'].includes(event.key)) next = (value ?? 0) <= 0.25 ? null : value - 0.25
        else if (event.key === 'Home') next = 0.25
        else if (event.key === 'End') next = 5
        else if (['Delete', 'Backspace'].includes(event.key)) next = null
        else return
        event.preventDefault(); setPreview(null); onChange(next)
      }}>
      {[1, 2, 3, 4, 5].map(score => <button type="button" tabIndex={-1} key={score} aria-label={`Elegir puntuación hasta ${score} de 5 en ${label}`}
        onPointerMove={event => { if (event.pointerType !== 'touch') setPreview(quarterAt(event, score)) }}
        onClick={event => { const next = quarterAt(event, score); setPreview(null); onChange(next); event.currentTarget.parentElement.focus({ preventScroll: true }) }}>
        {categoryKey === 'plot_twist'
          ? <Icon aria-hidden="true" fill="none" stroke="var(--rating-category-color)"
            strokeWidth={1.2 + 1.6 * Math.max(0, Math.min(1, (displayed ?? 0) - score + 1))}
            strokeLinecap="round" strokeLinejoin="round"
            style={{ width: 20, height: 20, verticalAlign: 'middle', fill: 'none', stroke: 'var(--rating-category-color)', opacity: (displayed ?? 0) > score - 1 ? 1 : 0.55, strokeWidth: 1.2 + 1.6 * Math.max(0, Math.min(1, (displayed ?? 0) - score + 1)) }} />
          : <PartialRatingIcon fraction={(displayed ?? 0) - score + 1} outline={icon(false)} filled={icon(true)} foreground={icon(false, (displayed ?? 0) > score - 1)} />}
      </button>)}
    </span>
    <span className={`library-rating-result${preview !== null ? ' is-preview' : ''}`}>
      <span className="library-rating-value" aria-live="polite">{displayed != null && displayed > 0 ? `${formatScore(displayed)} / 5` : '—'}</span>
      <button className="library-rating-clear" type="button" aria-label={`Quitar valoración de ${label}`} title="Quitar valoración" disabled={!selected} onClick={() => { setPreview(null); onChange(null) }}><X size={12} aria-hidden="true" /></button>
    </span>
  </div>
}
