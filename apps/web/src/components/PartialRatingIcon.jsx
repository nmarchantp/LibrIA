import './PartialRatingIcon.css'

export default function PartialRatingIcon({ fraction, outline, filled, foreground, size = 20 }) {
  const width = Math.max(0, Math.min(1, fraction)) * 100
  return <span className="partial-rating-icon" aria-hidden="true" style={{ '--partial-icon-size': `${size}px` }}>
    {!foreground && outline}
    <span className="partial-rating-fill" style={{ width: `${width}%` }}>{filled}</span>
    {foreground && <span className="partial-rating-foreground">{foreground}</span>}
  </span>
}
