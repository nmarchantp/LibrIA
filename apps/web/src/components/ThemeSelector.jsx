import { Check } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { themes } from '../theme/themes'
import './ThemeSelector.css'

export default function ThemeSelector() {
  const { theme, selectTheme } = useTheme()
  return <section className="profile-personalization" aria-labelledby="personalization-heading">
    <span className="kicker">TU ESPACIO, A TU MANERA</span>
    <h2 id="personalization-heading">Personalización</h2>
    <p>Elige los colores que acompañan tus lecturas. El tema se aplica a todo LibrIA.</p>
    <div className="theme-options" role="group" aria-label="Temas disponibles">
      {themes.map(item => <button key={item.id} type="button" className="theme-option" aria-pressed={theme === item.id} onClick={() => selectTheme(item.id)}>
        <span className="theme-swatches" aria-hidden="true">{item.colors.slice(0, 5).map(color => <span key={color} style={{ backgroundColor: color }} />)}</span>
        <span className="theme-option-name">{item.name}{theme === item.id && <Check size={18} aria-hidden="true" />}</span>
        <span className="theme-option-status">{theme === item.id ? 'Tema activo' : 'Elegir tema'}</span>
      </button>)}
    </div>
    <p className="theme-help">Tu elección se recuerda en este navegador. También puedes cambiarla en cualquier momento.</p>
  </section>
}
