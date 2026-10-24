import { Star } from 'lucide-react'

export default function RatingStar({ selected = false, ...props }) {
  const fill = selected ? 'var(--rating-star-color)' : 'none'
  return <Star {...props} aria-hidden="true" stroke="var(--rating-star-color)" strokeWidth={2.3} fill={fill}
    style={{ stroke: 'var(--rating-star-color)', strokeWidth: 2.3, fill, opacity: 1 }} />
}
