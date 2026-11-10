import { useState } from 'react'
import { Eye, EyeOff, TriangleAlert } from 'lucide-react'
import './SpoilerShield.css'

// Blurs spoiler content until the reader chooses to see it. Hidden content is
// inert, so it cannot be selected, focused or read by screen readers.
export default function SpoilerShield({ children, label = 'reseña' }) {
  const [revealed, setRevealed] = useState(false)
  if (revealed) return <div className="spoiler-shield is-revealed">
    {children}
    <button type="button" className="spoiler-hide" onClick={() => setRevealed(false)}><EyeOff size={14} aria-hidden="true" />Ocultar spoiler</button>
  </div>
  return <div className="spoiler-shield">
    <div className="spoiler-content" inert aria-hidden="true">{children}</div>
    <div className="spoiler-overlay">
      <span className="spoiler-badge"><TriangleAlert size={14} aria-hidden="true" />Esta {label} contiene spoilers</span>
      <p>Quien la escribió marcó detalles de la trama que podrían arruinarte la experiencia.</p>
      <button type="button" className="spoiler-reveal" onClick={() => setRevealed(true)}><Eye size={15} aria-hidden="true" />Mostrar de todos modos</button>
    </div>
  </div>
}
