// Separate closed continents keep oceans transparent in both rating states.
export default function WorldBuildingRatingIcon({ selected = false, strokeColor = 'var(--rating-category-color)', strokeWidth = 0.7 }) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"
    stroke={strokeColor} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <g strokeWidth={strokeWidth}>
      <path data-part="continent" fill={selected ? 'var(--rating-category-color)' : 'none'}
        d="M3.9 6.4C5.2 4.6 7.1 3.2 9.2 2.6L10.7 4.2L9.7 6.1L7.7 6.8L8.4 8.5L7.1 10.1L5 9.5L4.4 7.9Z" />
      <path data-part="continent" fill={selected ? 'var(--rating-category-color)' : 'none'}
        d="M6.1 12L8.5 12.3L10.5 14.4L10 16.4L8.7 17.7L8.2 20.1C6.8 18.6 6.8 16.8 6.9 15.4L5.5 13.8Z" />
      <path data-part="continent" fill={selected ? 'var(--rating-category-color)' : 'none'}
        d="M14.2 3.4C17.1 4.1 19.4 6.1 20.5 8.6L18.3 9.4L16.7 8.4L15.1 10.2L16.5 11.7L17.9 12.2L17.3 15L15.5 17.7L13.9 16.4L13.4 13.7L11.8 11.5L12.6 9.7L14 8.3L12.7 6.4Z" />
    </g>
    <circle cx="12" cy="12" r="10" fill="none" />
  </svg>
}
