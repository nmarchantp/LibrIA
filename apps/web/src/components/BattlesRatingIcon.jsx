const sword = 'M12 2L13.5 4V14H15V15.5H13V20H13.5V21.5H10.5V20H11V15.5H9V14H10.5V4Z'
const visualScale = 1.18

export default function BattlesRatingIcon({ selected = false, strokeColor = 'var(--rating-category-color)' }) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"
    stroke={strokeColor} strokeWidth={0.7} strokeLinecap="round" strokeLinejoin="round">
    {/* Expand the artwork inside its existing box; compensate the stroke so it stays fine. */}
    <g transform={`translate(12 12) scale(${visualScale}) translate(-12 -12)`} strokeWidth={0.7 / visualScale}>
    {[-45, 45].map(angle => <g key={angle} transform={`rotate(${angle} 12 12)`}>
      <path data-part="sword" d={sword} fill={selected ? 'var(--rating-category-color)' : 'none'} />
      <path data-part="blade-detail" d="M12 5V13" fill="none" />
    </g>)}
    </g>
  </svg>
}
