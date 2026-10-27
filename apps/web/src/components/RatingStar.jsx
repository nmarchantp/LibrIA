import { Star } from 'lucide-react'
import PartialRatingIcon from './PartialRatingIcon'

export default function RatingStar({ selected = false, fraction, ...props }) {
  if (fraction !== undefined) return <PartialRatingIcon fraction={fraction} size={props.size || 24}
    outline={<RatingStar {...props} />} filled={<RatingStar {...props} selected />} />
  const fill = selected ? 'var(--rating-star-color)' : 'none'
  return <Star {...props} aria-hidden="true" stroke="var(--rating-star-color)" strokeWidth={2.3} fill={fill}
    style={{ stroke: 'var(--rating-star-color)', strokeWidth: 2.3, fill, opacity: 1 }} />
}
