import './NavigationGalaxy.css'

/** Decorative layer only; navigation and accessible naming remain on the link. */
export default function NavigationGalaxy() {
  return <span className="navigation-galaxy" aria-hidden="true">
    {Array.from({ length: 6 }, (_, index) => <svg key={index} className={`navigation-galaxy-star navigation-galaxy-star--${index + 1}`} viewBox="0 0 20 20" focusable="false">
      <path d="M10 0c1.2 6.5 3.5 8.8 10 10-6.5 1.2-8.8 3.5-10 10C8.8 13.5 6.5 11.2 0 10 6.5 8.8 8.8 6.5 10 0Z" />
    </svg>)}
    <i className="navigation-galaxy-dust navigation-galaxy-dust--1" />
    <i className="navigation-galaxy-dust navigation-galaxy-dust--2" />
    <i className="navigation-galaxy-dust navigation-galaxy-dust--3" />
  </span>
}
