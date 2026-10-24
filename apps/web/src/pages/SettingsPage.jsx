import { Palette, UserRound } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import AccountPage from './AccountPage'
import ThemeSelector from '../components/ThemeSelector'
import useLiteraryPreferences from '../hooks/useLiteraryPreferences'
import './SettingsPage.css'

export default function SettingsPage() {
  const [params] = useSearchParams()
  const personalization = params.get('tab') === 'personalization'
  const preferences = useLiteraryPreferences()
  return <section className="page-width page settings-page" aria-labelledby="settings-heading">
    <span className="kicker">TU ESPACIO PERSONAL</span>
    <h1 className="page-title" id="settings-heading">Configuración</h1>
    <p className="settings-description">Tu espacio personal, a tu manera.</p>
    <nav className="settings-navigation" aria-label="Secciones de configuración">
      <Link to="/settings" className={!personalization ? 'selected' : ''} aria-current={!personalization ? 'page' : undefined}><UserRound size={18} aria-hidden="true" />Mi cuenta</Link>
      <Link to="/settings?tab=personalization" className={personalization ? 'selected' : ''} aria-current={personalization ? 'page' : undefined}><Palette size={18} aria-hidden="true" />Personalización</Link>
    </nav>
    {personalization ? <ThemeSelector /> : <AccountPage biography={preferences.data?.biography} />}
  </section>
}
