import './LiteraryIdentity.css'

// Static decoration, separate from content and excluded from assistive technology.
export default function LiteraryAtmosphere() {
  return <div className="literary-atmosphere" aria-hidden="true">
    <span className="literary-atmosphere-haze" />
    <span className="literary-atmosphere-star" />
    <span className="literary-atmosphere-star literary-atmosphere-star--distant" />
  </div>
}
