import './BrandLogo.css'

// Live SVG text preserves the official typeface and responds to theme variables.
export default function BrandLogo() {
  return <svg className="brand-logo" viewBox="28 24 442 136" role="img" aria-label="LibrIAverse · TU UNIVERSO LITERARIO" xmlns="http://www.w3.org/2000/svg">
    <g className="brand-logo-star">
      <path d="M263 29C265.5 42 271 48 286 51.5C271 55 265.5 61.5 263 75C260 61.5 254 55 240 51.5C254 48 260 42 263 29Z" />
      <path className="brand-logo-star-glint" d="M264 42C266 46 269 48.5 273 50" />
      <path className="brand-logo-orbit" d="M198 64C209 42 225 32 251 38" />
    </g>
    <text className="brand-logo-word" x="36" y="123" textLength="426" lengthAdjust="spacingAndGlyphs">Libr<tspan className="brand-logo-ai">IA</tspan>verse</text>
    <text className="brand-logo-tagline" x="242" y="151" textAnchor="middle" textLength="248" lengthAdjust="spacing">TU UNIVERSO LITERARIO</text>
  </svg>
}
