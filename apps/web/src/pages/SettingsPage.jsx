import { FileText, Palette, ShieldCheck, UserRound } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import AccountPage from './AccountPage'
import ThemeSelector from '../components/ThemeSelector'
import useLiteraryPreferences from '../hooks/useLiteraryPreferences'
import './SettingsPage.css'
import { useAuth } from '../context/AuthContext'
import ModerationSection from '../components/ModerationSection'
import PrivateModerationStatus from '../components/PrivateModerationStatus'
import ProfilePrivacySettings from '../components/ProfilePrivacySettings'

export default function SettingsPage() {
  const [params] = useSearchParams()
  const personalization = params.get('tab') === 'personalization'
  const { user, access, accessLoading } = useAuth()
  const canModerate = !accessLoading && access?.admin
  const moderation = canModerate && params.get('tab') === 'moderation'
  const publications = params.get('tab') === 'publications'
  const preferences = useLiteraryPreferences()
  return <section className="page-width page settings-page" aria-labelledby="settings-heading">
    <span className="kicker">TU ESPACIO PERSONAL</span>
    <h1 className="page-title" id="settings-heading">Configuración</h1>
    <p className="settings-description">Tu espacio personal, a tu manera.</p>
    <nav className="settings-navigation" aria-label="Secciones de configuración">
      <Link to="/settings" className={!personalization && !moderation && !publications ? 'selected' : ''} aria-current={!personalization && !moderation && !publications ? 'page' : undefined}><UserRound size={18} aria-hidden="true" />Mi cuenta</Link>
      <Link to="/settings?tab=personalization" className={personalization ? 'selected' : ''} aria-current={personalization ? 'page' : undefined}><Palette size={18} aria-hidden="true" />Personalización</Link>
      <Link to="/settings?tab=publications" className={publications ? 'selected' : ''} aria-current={publications ? 'page' : undefined}><FileText size={18} aria-hidden="true" />Estado de publicaciones</Link>
      {canModerate && <Link to="/settings?tab=moderation" className={moderation ? 'selected' : ''} aria-current={moderation ? 'page' : undefined}><ShieldCheck size={18} aria-hidden="true" />Moderación de contenido</Link>}
    </nav>
    {publications ? <PrivateModerationStatus key={user.id} userId={user.id} /> : moderation ? <ModerationSection initiallyOpen /> : personalization ? <ThemeSelector /> : <><AccountPage biography={preferences.data?.biography} /><ProfilePrivacySettings preferences={preferences} /></>}
  </section>
}
