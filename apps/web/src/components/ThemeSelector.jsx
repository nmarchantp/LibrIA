import { Check } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { themes } from '../theme/themes'
import { useState } from 'react'
import { onboardingService } from '../services/onboardingService'
import VisualEffectsSettings from './VisualEffectsSettings'
import './ThemeSelector.css'

export default function ThemeSelector() {
  const { theme, selectTheme } = useTheme()
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const choose = async id => {
    if (saving) return
    setSaving(true); setError('')
    selectTheme(id)
    try { if (localStorage.getItem('libria_token')) await onboardingService.theme(id) }
    catch (error) { setError(error.message) }
    finally { setSaving(false) }
  }
  return <section className="profile-personalization" aria-labelledby="personalization-heading">
    <h2 id="personalization-heading">Elige tu universo</h2>
    <p className="personalization-description">Cada universo tiene su propia magia. Descubre la tuya.</p>
    <div className="theme-options" role="group" aria-labelledby="personalization-heading">
      {themes.map(item => <button key={item.id} type="button" className="theme-option" data-theme-option={item.id} aria-pressed={theme === item.id} disabled={saving} onClick={() => choose(item.id)}>
        <span className="theme-swatches" aria-hidden="true" style={{ backgroundImage: `linear-gradient(135deg, ${item.colors.slice(0, 5).join(', ')})` }} />
        <span className="theme-option-name">{item.name}</span>
        <span className="theme-option-check" aria-hidden="true">{theme === item.id && <Check size={18} />}</span>
      </button>)}
    </div>
    {error && <p role="alert">{error}</p>}
    <VisualEffectsSettings />
  </section>
}
