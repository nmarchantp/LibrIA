import { Check } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { themes } from '../theme/themes'
import VisualEffectsSettings from './VisualEffectsSettings'
import './ThemeSelector.css'

export default function ThemeSelector() {
  const { theme, selectTheme } = useTheme()
  return <section className="profile-personalization" aria-labelledby="personalization-heading">
    <h2 id="personalization-heading">Elige tu universo</h2>
    <p className="personalization-description">Cada universo tiene su propia magia. Descubre la tuya.</p>
    <div className="theme-options" role="group" aria-labelledby="personalization-heading">
      {themes.map(item => <button key={item.id} type="button" className="theme-option" data-theme-option={item.id} aria-pressed={theme === item.id} onClick={() => selectTheme(item.id)}>
        <span className="theme-swatches" aria-hidden="true" style={{ backgroundImage: `linear-gradient(135deg, ${item.colors.slice(0, 5).join(', ')})` }} />
        <span className="theme-option-name">{item.name}</span>
        <span className="theme-option-check" aria-hidden="true">{theme === item.id && <Check size={18} />}</span>
      </button>)}
    </div>
    <VisualEffectsSettings />
  </section>
}
