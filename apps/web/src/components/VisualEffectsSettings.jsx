import { useId } from 'react'
import { useTheme } from '../context/ThemeContext'

export default function VisualEffectsSettings() {
  const { magicalBackground, setMagicalBackground } = useTheme()
  const id = useId()
  return <section className="visual-effects-settings" aria-labelledby={`${id}-heading`}>
    <h3 id={`${id}-heading`}>Fondo mágico</h3>
    <div className="visual-effects-setting">
      <p className="personalization-description" id={`${id}-description`}>Muestra el efecto decorativo en todas las vistas de LibrIAverse.</p>
      <span className="visual-effects-switch">
        <input id={id} type="checkbox" role="switch" checked={magicalBackground} aria-labelledby={`${id}-heading`} aria-describedby={`${id}-description`} onChange={event => setMagicalBackground(event.target.checked)} />
        <span aria-hidden="true" />
      </span>
    </div>
  </section>
}
