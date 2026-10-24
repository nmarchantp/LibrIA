import './NavigationIcon.css'

/** Decorative SVGs: the parent navigation link supplies the accessible name. */
export default function NavigationIcon({ variant }) {
  return <svg className={`navigation-icon navigation-icon--${variant}`} width="22" height="22" viewBox="0 0 28 28" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {variant === 'book' ? <>
      <path className="navigation-icon-cover" d="M3 7v16c4-1 7-.5 11 1 4-1.5 7-2 11-1V7" />
      <g className="navigation-icon-page navigation-icon-page--left">
        <path d="M14 23V7C11 4.8 7.5 4 3 5v15c4-1 7.5 0 11 3Z" />
        <path className="navigation-icon-ink" d="m6.5 9 4 1M6.5 13l4 1" />
      </g>
      <g className="navigation-icon-page navigation-icon-page--right">
        <path d="M14 23V7c3-2.2 6.5-3 11-2v15c-4-1-7.5 0-11 3Z" />
        <path className="navigation-icon-ink" d="m17.5 10 4-1m-4 5 4-1" />
      </g>
      <path className="navigation-icon-glint" d="m14 1 .6 1.6L16 3l-1.4.5L14 5l-.6-1.5L12 3l1.4-.4Z" />
    </> : <>
      <g className="navigation-icon-wand">
        <path d="m5 24-1-1a1.4 1.4 0 0 1 0-2l13-13 3 3L7 24a1.4 1.4 0 0 1-2 0Z" />
        <path d="m14.5 10.5 3 3" />
      </g>
    </>}
  </svg>
}
