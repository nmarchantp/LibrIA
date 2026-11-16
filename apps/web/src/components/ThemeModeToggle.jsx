import { useId } from 'react'
import { Sun, Moon } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { themes } from '../theme/themes'

export default function ThemeModeToggle() {
  const { theme, selectTheme } = useTheme()
  const tooltip = useId()
  const dark = themes.find(item => item.id === theme)?.group === 'dark'
  const label = dark ? 'Cambiar a modo claro: Jardín de Macarons' : 'Cambiar a modo oscuro: Reino de Sombras'
  const Icon = dark ? Sun : Moon
  return <button type="button" className="global-header-action" aria-label={label} aria-describedby={tooltip} title={label} onClick={() => selectTheme(dark ? 'lavanda' : 'dark')}>
    <Icon size={21} aria-hidden="true" /><span id={tooltip} className="global-header-tooltip" role="tooltip">{label}</span>
  </button>
}
