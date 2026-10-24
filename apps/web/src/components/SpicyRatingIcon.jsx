export default function SpicyRatingIcon({ selected = false }) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"
    stroke="var(--rating-category-color)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
    <path data-part="outer-flame" fill={selected ? 'var(--rating-category-color)' : 'none'}
      d="M8 2.5C13.5 2.6 19.8 8.6 19.8 14.2C19.8 18.8 16.6 21.5 12 21.5C7.5 21.5 4.6 18.7 4.6 14.8C4.6 11.9 6.4 9.8 7.2 7.8C8.3 8.5 8.9 9.5 8.9 10.7C11 8.1 10 5.1 8 2.5Z" />
    <path data-part="inner-flame" fill={selected ? '#C44516' : 'none'} stroke={selected ? '#C44516' : 'var(--rating-category-color)'} strokeWidth={1.2}
      d="M10.9 10.4C14.7 12.5 16.1 15 14.8 17.4C14.1 18.7 12.3 19.2 11 18.2C9.5 17 10.3 15.5 11 14.2C11.7 12.9 11.7 11.7 10.9 10.4Z" />
  </svg>
}
