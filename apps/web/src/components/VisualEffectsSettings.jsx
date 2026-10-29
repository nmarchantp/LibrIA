import { useId } from 'react'
import { useTheme } from '../context/ThemeContext'

export default function VisualEffectsSettings() {
  const { magicalBackground, setMagicalBackground, magicalBackgroundMotion, setMagicalBackgroundMotion } = useTheme()
  const id = useId()
  const motionId = `${id}-motion`
  return <section className="visual-effects-settings" aria-labelledby={`${id}-heading`}>
    <h3 id={`${id}-heading`}>Fondo mágico</h3>
    <div className="visual-effects-setting">
      <p className="personalization-description" id={`${id}-description`}>Muestra el efecto decorativo en todas las vistas de LibrIAverse.</p>
      <span className="visual-effects-switch">
        <input id={id} type="checkbox" role="switch" checked={magicalBackground} aria-labelledby={`${id}-heading`} aria-describedby={`${id}-description`} onChange={event => setMagicalBackground(event.target.checked)} />
        <span aria-hidden="true" />
      </span>
    </div>
    <div className={`visual-effects-setting visual-effects-motion${magicalBackground ? '' : ' is-disabled'}`}>
      <p className="personalization-description" id={`${motionId}-description`}>
        <strong id={`${motionId}-heading`}>Mover los puntitos</strong>
        <span>Activa o pausa el movimiento de las partículas sobre el fondo mágico.</span>
      </p>
      <span className="visual-effects-switch">
        <input id={motionId} type="checkbox" role="switch" checked={magicalBackground && magicalBackgroundMotion} disabled={!magicalBackground} aria-labelledby={`${motionId}-heading`} aria-describedby={`${motionId}-description`} onChange={event => setMagicalBackgroundMotion(event.target.checked)} />
        <span aria-hidden="true" />
      </span>
    </div>
  </section>
}
